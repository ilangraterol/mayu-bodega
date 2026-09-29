"""Shared helpers for the maintenance scripts in ``backend/tools``.

Every tool here is a diagnostic or a repair utility for local development.
They are intentionally *not* Django management commands: they are meant to be
run ad hoc (``python tools/<script>.py``) and reused instead of rewritten.

Rules that every tool in this folder obeys:

* **Read only by default.** Anything that writes to the database or unlinks a
  file requires an explicit ``--apply`` flag and prints a plan first.
* **No hardcoded credentials.** Passwords come from ``MAYU_PASSWORD`` or an
  interactive prompt; nothing is ever written to disk or printed.
* **Reuse before writing.** If a new investigation is needed, add a flag to the
  closest existing tool or add a new documented tool here, never a stray
  throwaway script next to ``manage.py``.
"""

from __future__ import annotations

import getpass
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_API_URL = os.environ.get('MAYU_API_URL', 'http://127.0.0.1:8000')
DEFAULT_USERNAME = os.environ.get('MAYU_USERNAME', 'admin')
LOGIN_PATH = '/api/core/auth/login/'


def setup_django() -> None:
    """Configure Django so the ORM is importable from a plain script."""
    if BACKEND_DIR.as_posix() not in sys.path:
        sys.path.insert(0, BACKEND_DIR.as_posix())
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django

    django.setup()


def api_password() -> str:
    """Resolve the API password without ever persisting it."""
    password = os.environ.get('MAYU_PASSWORD')
    if password:
        return password
    if sys.stdin.isatty():
        return getpass.getpass(f'Contraseña de {DEFAULT_USERNAME}: ')
    raise SystemExit(
        'Falta la variable de entorno MAYU_PASSWORD. Defínela antes de ejecutar '
        ' este script.'
    )


def api_session(api_url: str = DEFAULT_API_URL, username: str | None = None):
    """Return ``(base_url, token)`` for an authenticated API client."""
    username = username or DEFAULT_USERNAME
    url = api_url.rstrip('/')
    payload = urllib.parse.urlencode(
        {'username': username, 'password': api_password()}
    ).encode()
    request = urllib.request.Request(
        url + LOGIN_PATH, data=payload, method='POST'
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.URLError as error:
        raise SystemExit(
            f'No se pudo conectar con {url}. ¿El servidor está corriendo?\n  {error}'
        ) from error
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f'Login rechazado ({error.code}). Revise usuario y contraseña.'
        ) from error

    import json

    token = json.loads(body).get('token')
    if not token:
        raise SystemExit('La respuesta de login no incluyó un token.')
    return url, token


def request(
    method: str,
    url: str,
    token: str | None = None,
    data: bytes | None = None,
    headers: dict | None = None,
    timeout: int = 30,
):
    """Perform an HTTP call, returning ``(status_code, body_text)``.

    Errors are returned instead of raised so tools can report a broken URL
    rather than crash halfway through a catalogue scan.
    """
    all_headers = {'Accept': 'application/json'}
    if token:
        all_headers['Authorization'] = f'Token {token}'
    all_headers.update(headers or {})

    req = urllib.request.Request(url, data=data, method=method, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8', 'replace')
    except urllib.error.URLError as error:
        return 0, str(error)


def multipart(fields: dict, file_field: str, filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for an image upload."""
    boundary = '----mayu-bodega-tools-boundary'
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'
            f'{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
    )
    parts.append(content)
    parts.append(f'\r\n--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def heading(text: str) -> None:
    print(f'\n{text}')
    print('-' * len(text))


def ok(text: str) -> None:
    print(f'  [ok]   {text}')


def warn(text: str) -> None:
    print(f'  [aviso] {text}')


def fail(text: str) -> None:
    print(f'  [FALLA] {text}')


def require_apply(apply: bool, description: str) -> None:
    """Abort a mutating tool unless the operator opted in explicitly."""
    if apply:
        return
    print(f'Operación destructiva bloqueada: {description}')
    print('Revise el plan anterior y vuelva a ejecutar con --apply si es correcto.')
    raise SystemExit(1)
