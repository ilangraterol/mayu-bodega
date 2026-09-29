"""Tests for the BCV reader.

The parser is exercised against a trimmed copy of the official page so the suite
never touches the network.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from rates.models import ExchangeRate
from rates.services import (
    BcvRateNotDue,
    BcvSyncError,
    _format_moment,
    _parse_bcv_html,
    bcv_sync_status,
    sync_bcv_rate,
)

BCV_HTML = """
<html><body>
  <div class="row recuadrotsmc"><div class="col-sm-6">Tasas<div class="textp">
    <strong class="strong-tb">10,15290046</strong></div></div>
  <div id="dolar" class="col-sm-12 col-xs-12 ">
    <div class="field-content">
      <div class="row recuadrotsmc">
        <div class="col-sm-6 col-xs-6">
          <img src="/sites/default/files/dollar-04_2.png" class="icono_bss_blanco1">
          <span> USD</span>
        </div>
        <div class="col-sm-6 col-xs-6 centrado textp">
          <strong class="strong-tb">857,88760000</strong>
        </div>
      </div>
    </div>
  </div>
  <div class="pull-right dinpro center">
    Fecha Valor: <span class="date-display-single" property="dc:date"
      datatype="xsd:dateTime" content="2026-09-29T00:00:00-04:00">Martes, 29 Septiembre 2026</span>
    <hr>
  </div>
</body></html>
"""


class ParseBcvHtmlTests(TestCase):
    def test_reads_rate_and_effective_date(self):
        rate, effective_date = _parse_bcv_html(BCV_HTML)

        self.assertEqual(rate, Decimal('857.8876'))
        self.assertEqual(effective_date, date(2026, 9, 29))

    def test_does_not_pick_the_previous_rate_block(self):
        html = BCV_HTML.replace('857,88760000', '912,00000000')

        rate, _ = _parse_bcv_html(html)

        self.assertEqual(rate, Decimal('912.0000'))

    def test_missing_rate_raises(self):
        with self.assertRaises(BcvSyncError):
            _parse_bcv_html('<html><body><div id="dolar"></div></body></html>')

    def test_missing_date_raises(self):
        html = BCV_HTML.split('Fecha Valor:')[0]

        with self.assertRaises(BcvSyncError):
            _parse_bcv_html(html)

    def test_zero_rate_raises(self):
        html = BCV_HTML.replace('857,88760000', '0,00000000')

        with self.assertRaises(BcvSyncError):
            _parse_bcv_html(html)


class SyncBcvRateTests(TestCase):
    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_stores_rate_once_per_effective_date(self):
        from unittest.mock import patch

        payload = (Decimal('857.8876'), date(2026, 9, 29))
        with patch('rates.services.fetch_bcv_rate', return_value=payload) as fetch:
            created = sync_bcv_rate()
            self.assertTrue(created.pk)
            self.assertEqual(created.rate, Decimal('857.8876'))
            self.assertEqual(created.source, ExchangeRate.Source.BCV)
            self.assertEqual(ExchangeRate.objects.count(), 1)

        with patch('rates.services.fetch_bcv_rate', return_value=payload):
            second = sync_bcv_rate(force=True)

        self.assertEqual(second.pk, created.pk)
        self.assertEqual(ExchangeRate.objects.count(), 1)
        self.assertEqual(fetch.call_count, 1)

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_refreshing_the_same_day_moves_the_last_read_forward(self):
        from unittest.mock import patch

        payload = (Decimal('857.8876'), date(2026, 9, 29))
        with patch('rates.services.fetch_bcv_rate', return_value=payload):
            first = sync_bcv_rate()

        ExchangeRate.objects.filter(pk=first.pk).update(
            fetched_at=timezone.now() - timedelta(minutes=30)
        )

        with patch('rates.services.fetch_bcv_rate', return_value=payload):
            second = sync_bcv_rate(force=True)

        self.assertGreater(second.fetched_at, first.fetched_at - timedelta(seconds=1))
        # A moment of wall-clock passes between the write and the read.
        self.assertAlmostEqual(bcv_sync_status()['seconds_until_next_sync'], 900, delta=2)

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_second_run_inside_window_is_skipped(self):
        from unittest.mock import patch

        payload = (Decimal('857.8876'), date(2026, 9, 29))
        with patch('rates.services.fetch_bcv_rate', return_value=payload):
            sync_bcv_rate()

        with patch('rates.services.fetch_bcv_rate', return_value=payload) as fetch:
            with self.assertRaises(BcvRateNotDue):
                sync_bcv_rate()
        fetch.assert_not_called()
        self.assertEqual(ExchangeRate.objects.count(), 1)

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=0)
    def test_zero_window_always_queries(self):
        from unittest.mock import patch

        payload = (Decimal('857.8876'), date(2026, 9, 29))
        with patch('rates.services.fetch_bcv_rate', return_value=payload):
            sync_bcv_rate()
        with patch('rates.services.fetch_bcv_rate', return_value=payload) as fetch:
            sync_bcv_rate()

        fetch.assert_called_once()


class BcvSyncStatusTests(TestCase):
    def _seed(self, minutes_ago: int) -> ExchangeRate:
        rate = ExchangeRate.objects.create(
            source=ExchangeRate.Source.BCV,
            rate=Decimal('857.8876'),
            effective_date=date(2026, 9, 29),
        )
        # `fetched_at` is `auto_now_add`, so it can only be backdated with a query.
        ExchangeRate.objects.filter(pk=rate.pk).update(
            fetched_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        rate.refresh_from_db()
        return rate

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_counts_down_in_seconds_while_cooling_down(self):
        self._seed(minutes_ago=5)

        status = bcv_sync_status()

        self.assertFalse(status['can_sync'])
        self.assertGreater(status['seconds_until_next_sync'], 540)
        self.assertLessEqual(status['seconds_until_next_sync'], 601)
        self.assertIsNotNone(status['last_fetched_at'])

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_allows_sync_once_the_window_passes(self):
        self._seed(minutes_ago=20)

        status = bcv_sync_status()

        self.assertTrue(status['can_sync'])
        self.assertEqual(status['seconds_until_next_sync'], 0)

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_manual_rates_do_not_start_the_cooldown(self):
        ExchangeRate.objects.create(
            source=ExchangeRate.Source.MANUAL,
            rate=Decimal('857.8800'),
            effective_date=date(2026, 9, 29),
        )

        status = bcv_sync_status()

        self.assertTrue(status['can_sync'])
        self.assertIsNone(status['last_fetched_at'])

    def test_moment_uses_the_requested_format(self):
        moment = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0)

        formatted = _format_moment(moment)

        self.assertRegex(formatted, r'^\d{2}/\d{2}/\d{4} 11:00 (am|pm)$')

    def test_midnight_and_noon_use_twelve_hour_clock(self):
        midnight = timezone.localtime().replace(hour=0, minute=5, second=0, microsecond=0)
        noon = timezone.localtime().replace(hour=12, minute=5, second=0, microsecond=0)
        evening = timezone.localtime().replace(hour=20, minute=7, second=0, microsecond=0)

        self.assertIn('12:05 am', _format_moment(midnight))
        self.assertIn('12:05 pm', _format_moment(noon))
        self.assertIn('8:07 pm', _format_moment(evening))

    @override_settings(BCV_RATE_MIN_INTERVAL_SECONDS=900)
    def test_cooldown_message_reports_moment_and_minutes(self):
        self._seed(minutes_ago=4)

        with self.assertRaises(BcvRateNotDue) as caught:
            sync_bcv_rate()

        message = str(caught.exception)
        self.assertRegex(message, r'\d{2}/\d{2}/\d{4} \d{1,2}:\d{2} (am|pm)')
        self.assertIn('próxima consulta estará disponible en', message)
        self.assertIn('min.', message)
        self.assertNotIn('900 segundos', message)
