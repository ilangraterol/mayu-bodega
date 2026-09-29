"""Exchange rate domain services.

Responsibilities kept out of views and serializers:

* read the current rate (``get_current_rate``);
* sync the BCV official rate (``sync_bcv_rate``);
* register an administrator's manual fallback rate (``register_manual_rate``).

Upstream notes: the former ``mippetro.bcv.org.ve/getDocument/index/3`` JSON
endpoint no longer resolves, so the official rate is read from the BCV site
itself. Every sync performs exactly one request and refuses to run twice inside
``BCV_RATE_MIN_INTERVAL_SECONDS``.
"""

import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.money import quantize_rate
from rates.models import ExchangeRate, MissingExchangeRateError

logger = logging.getLogger(__name__)

_DATE_FORMATS = ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%y')

_RATE_BLOCK = re.compile(r'<div\s+id="dolar"', re.IGNORECASE)
_RATE_BLOCK_LOOKAHEAD = 2500
_RATE_VALUE = re.compile(
    r'<strong[^>]*class="[^"]*strong-tb[^"]*"[^>]*>\s*(?P<rate>[0-9][0-9.,\s]*?)\s*</strong>',
    re.IGNORECASE,
)
_EFFECTIVE_DATE = re.compile(
    r'property="dc:date"[^>]*?content="(?P<day>\d{4}-\d{2}-\d{2})',
    re.IGNORECASE,
)
_VALUE_DATE = re.compile(
    r'Fecha\s*Valor:.{0,400}?content="(?P<day>\d{4}-\d{2}-\d{2})',
    re.IGNORECASE | re.DOTALL,
)


class BcvSyncError(RuntimeError):
    """The BCV source could not be read."""


class BcvRateNotDue(BcvSyncError):
    """A sync was requested inside the minimum interval, so no request was made."""


def get_current_rate(required: bool = True) -> ExchangeRate:
    rate = ExchangeRate.objects.current()
    if rate is None and required:
        raise MissingExchangeRateError(
            'No hay tasa de cambio registrada. Ejecute la sincronización del BCV o registre una tasa manual.'
        )
    return rate


def get_rate_for_date(day: date, required: bool = True) -> ExchangeRate:
    """Rate in force on ``day``.

    Falls back to the closest rate published on or before that day, so a payment
    registered on a day the BCV did not publish still gets the last known rate.
    """
    rate = ExchangeRate.objects.filter(effective_date__lte=day).current()
    if rate is None:
        rate = ExchangeRate.objects.current()
    if rate is None and required:
        raise MissingExchangeRateError(
            'No hay tasa de cambio registrada. Ejecute la sincronización del BCV o registre una tasa manual.'
        )
    return rate


def _parse_date(raw: str) -> date:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise BcvSyncError(f'Formato de fecha no reconocido en la respuesta del BCV: {raw!r}')


def _bcv_session() -> requests.Session:
    """Session that trusts the CA bundle plus the BCV intermediate certificate."""
    session = requests.Session()
    try:
        import certifi
    except ImportError:
        return session

    intermediate = Path(getattr(settings, 'BCV_RATE_CA_BUNDLE', '') or '')
    if not intermediate.is_file():
        logger.warning('No se encontro el intermedio del BCV en %s.', intermediate)
        return session

    bundle = _build_ca_bundle(intermediate)
    if bundle is not None:
        session.verify = str(bundle)
    return session


def _build_ca_bundle(intermediate: Path) -> Path | None:
    """Write certifi roots plus the intermediate to a combined PEM bundle."""
    import certifi

    cache_dir = Path(settings.BASE_DIR) / 'rates' / 'certs' / '.cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / 'bcv-ca-bundle.pem'

    stamp = target.with_suffix('.stamp')
    roots = Path(certifi.where())
    signature = f'{roots.stat().st_mtime_ns}:{intermediate.stat().st_mtime_ns}'
    if target.exists() and stamp.exists() and stamp.read_text(encoding='ascii').strip() == signature:
        return target

    parts = [roots.read_text(encoding='ascii'), intermediate.read_text(encoding='ascii')]
    target.write_text('\n'.join(parts), encoding='ascii')
    stamp.write_text(signature, encoding='ascii')
    return target


def _parse_bcv_html(html: str) -> tuple[Decimal, date]:
    """Extract ``(rate, effective_date)`` from the official BCV page."""
    block_match = _RATE_BLOCK.search(html)
    if block_match:
        block = html[block_match.start(): block_match.start() + _RATE_BLOCK_LOOKAHEAD]
    else:
        block = html

    value_match = _RATE_VALUE.search(block)
    if not value_match:
        raise BcvSyncError('No se encontró la tasa del dólar en la página del BCV.')

    raw_rate = value_match.group('rate')
    try:
        rate = quantize_rate(Decimal(raw_rate.replace(' ', '').replace('.', '').replace(',', '.')))
    except (InvalidOperation, ValueError) as error:
        raise BcvSyncError(f'Precio del dólar inválido en el BCV: {raw_rate!r}') from error
    if rate <= 0:
        raise BcvSyncError(f'Precio del dólar inválido en el BCV: {raw_rate!r}')

    day_match = _VALUE_DATE.search(html) or _EFFECTIVE_DATE.search(html)
    if not day_match:
        raise BcvSyncError('No se encontró la fecha de vigencia publicada por el BCV.')

    try:
        effective_date = date.fromisoformat(day_match.group('day'))
    except ValueError as error:
        raise BcvSyncError(f'Fecha de vigencia inválida en el BCV: {day_match.group("day")!r}') from error

    return rate, effective_date


def _should_skip_upstream() -> bool:
    """True when we already read a BCV rate inside the configured window."""
    window = timedelta(seconds=getattr(settings, 'BCV_RATE_MIN_INTERVAL_SECONDS', 900))
    if window.total_seconds() <= 0:
        return False
    latest = ExchangeRate.objects.filter(source=ExchangeRate.Source.BCV).order_by('-fetched_at').first()
    if latest is None:
        return False
    return timezone.now() - latest.fetched_at < window


def fetch_bcv_rate() -> tuple[Decimal, date]:
    """Read the official rate. Performs exactly one upstream request."""
    url = settings.BCV_RATE_URL
    session = _bcv_session()
    try:
        response = session.get(
            url,
            timeout=settings.BCV_RATE_TIMEOUT_SECONDS,
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-VE,es;q=0.9',
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
                ),
            },
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise BcvSyncError(f'No se pudo consultar el BCV: {error}') from error

    content_type = response.headers.get('Content-Type', '').lower()
    if 'json' in content_type:
        return _parse_bcv_json(response)
    return _parse_bcv_html(response.text)


def _parse_bcv_json(response: requests.Response) -> tuple[Decimal, date]:
    """Kept for a JSON mirror if ``BCV_RATE_URL`` is pointed at one."""
    try:
        payload = response.json()
    except ValueError as error:
        raise BcvSyncError(f'Respuesta inválida del BCV: {error}') from error
    if not isinstance(payload, dict):
        raise BcvSyncError('La respuesta del BCV no es un objeto JSON.')

    raw_rate = payload.get('price') or payload.get('pricebcv')
    if raw_rate in (None, ''):
        raise BcvSyncError('La respuesta del BCV no incluye el precio del dólar.')
    try:
        rate = quantize_rate(Decimal(str(raw_rate).replace(',', '.')))
    except (InvalidOperation, ValueError) as error:
        raise BcvSyncError(f'Precio del dólar inválido: {raw_rate!r}') from error
    if rate <= 0:
        raise BcvSyncError(f'Precio del dólar inválido: {raw_rate!r}')

    raw_date = payload.get('fecha') or payload.get('date')
    effective_date = _parse_date(raw_date) if raw_date else date.today()
    return rate, effective_date


def _format_moment(moment) -> str:
    """`29/08/2026 11:00 am`, the way the shop reads a moment out loud."""
    local = timezone.localtime(moment)
    hours = local.strftime('%I').lstrip('0') or '0'
    return f'{local:%d/%m/%Y} {hours}:{local:%M} {local:%p}'.lower()


def bcv_sync_status() -> dict:
    """When the BCV was last read and when the next read is allowed."""
    min_interval = int(getattr(settings, 'BCV_RATE_MIN_INTERVAL_SECONDS', 900))
    latest = ExchangeRate.objects.filter(source=ExchangeRate.Source.BCV).order_by('-fetched_at').first()

    if latest is None or min_interval <= 0:
        return {
            'last_fetched_at': None,
            'min_interval_seconds': min_interval,
            'seconds_until_next_sync': 0,
            'next_sync_available_at': None,
            'can_sync': True,
        }

    available_at = latest.fetched_at + timedelta(seconds=min_interval)
    seconds_left = max(0, int((available_at - timezone.now()).total_seconds()))
    return {
        'last_fetched_at': latest.fetched_at,
        'min_interval_seconds': min_interval,
        'seconds_until_next_sync': seconds_left,
        'next_sync_available_at': available_at,
        'can_sync': seconds_left == 0,
    }


def _cooldown_message() -> str:
    status = bcv_sync_status()
    minutes = max(1, round(status['seconds_until_next_sync'] / 60))
    return (
        f'Ya se consultó el BCV el {_format_moment(status["last_fetched_at"])}. '
        f'La próxima consulta estará disponible en {minutes} min.'
    )


@transaction.atomic
def sync_bcv_rate(force: bool = False) -> ExchangeRate:
    """Store today's official rate, keeping the published date as effective date."""
    if not force and _should_skip_upstream():
        raise BcvRateNotDue(_cooldown_message())

    rate, effective_date = fetch_bcv_rate()

    exchange_rate, created = ExchangeRate.objects.update_or_create(
        source=ExchangeRate.Source.BCV,
        effective_date=effective_date,
        # `fetched_at` is `auto_now_add`, so it is only set on insert. Refreshing it
        # here keeps it meaning "when we last read the BCV", which is what the
        # cooldown counts from.
        defaults={'rate': rate, 'is_active': True, 'fetched_at': timezone.now()},
    )
    logger.info('Tasa BCV %s guardada (%s).', rate, 'creada' if created else 'actualizada')
    return exchange_rate


@transaction.atomic
def register_manual_rate(rate, effective_date: date, user, notes: str = '') -> ExchangeRate:
    """Administrator fallback. It never overwrites an official BCV row."""
    try:
        value = quantize_rate(Decimal(str(rate)))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f'Tasa inválida: {rate!r}') from error
    if value <= 0:
        raise ValueError('La tasa debe ser mayor que cero.')

    exchange_rate, _ = ExchangeRate.objects.update_or_create(
        source=ExchangeRate.Source.MANUAL,
        effective_date=effective_date,
        defaults={
            'rate': value,
            'is_active': True,
            'recorded_by': user if getattr(user, 'is_authenticated', False) else None,
            'notes': notes[:255],
        },
    )
    return exchange_rate
