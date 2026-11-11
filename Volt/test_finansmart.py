from decimal import Decimal
import io
import json
import socket
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.test import RequestFactory, TestCase, override_settings

from Volt.domain.finance import FinanceSummary, FinanceSummaryProvider
from Volt.infra.factory import (
    FinanceSummaryProviderFactory,
    create_finance_summary_provider,
)
from Volt.infra.fake_finance import FakeFinanceSummaryProvider
from Volt.infra.finansmart_adapter import FinanSmartAdapter
from Volt.views import finansmart_summary


class FinanceDomainAndFakeTests(TestCase):
    def test_finance_summary_provider_is_abstract(self):
        with self.assertRaises(TypeError):
            FinanceSummaryProvider()

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_fake_provider_returns_summary_without_network(self, mock_urlopen):
        provider = FakeFinanceSummaryProvider()
        summary = provider.get_summary()

        mock_urlopen.assert_not_called()
        self.assertIsInstance(summary, FinanceSummary)
        self.assertEqual(summary.month, 11)
        self.assertEqual(summary.year, 2026)
        self.assertEqual(summary.currency, 'COP')
        self.assertEqual(summary.income, Decimal('3200000.00'))
        self.assertEqual(summary.expenses, Decimal('245000.00'))
        self.assertEqual(summary.balance, Decimal('2955000.00'))
        self.assertEqual(summary.savings, Decimal('1250000.00'))
        self.assertEqual(summary.debt, Decimal('1800000.00'))
        self.assertEqual(summary.source, 'Datos de demostración (simulado)')
        for field_name in ('income', 'expenses', 'balance', 'savings', 'debt'):
            self.assertIsInstance(getattr(summary, field_name), Decimal)

    def test_fake_provider_supports_negative_balance_and_unavailable_mode(self):
        negative_summary = FinanceSummary(
            month=10,
            year=2026,
            currency='COP',
            income=Decimal('1000000.00'),
            expenses=Decimal('1350000.00'),
            balance=Decimal('-350000.00'),
            savings=Decimal('200000.00'),
            debt=Decimal('500000.00'),
        )
        provider_neg = FakeFinanceSummaryProvider(summary=negative_summary)
        self.assertEqual(provider_neg.get_summary().balance, Decimal('-350000.00'))

        provider_down = FakeFinanceSummaryProvider(available=False)
        self.assertIsNone(provider_down.get_summary())


@override_settings(
    FINANSMART_SUMMARY_URL='http://finansmart.local/api/v1/summary/',
    FINANSMART_TOKEN='secret-ally-token-999',
)
class FinanSmartAdapterHttpTests(TestCase):
    def _mock_http_200(self, payload_bytes: bytes) -> MagicMock:
        response = MagicMock()
        response.status = 200
        response.read.return_value = payload_bytes
        context_manager = MagicMock()
        context_manager.__enter__.return_value = response
        context_manager.__exit__.return_value = False
        return context_manager

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_http_200_parses_contract_and_converts_amounts_to_decimal(self, mock_urlopen):
        payload = {
            'month': 11,
            'year': 2026,
            'currency': 'COP',
            'income': '3200000.00',
            'expenses': '245000.00',
            'balance': '2955000.00',
            'savings': '1250000.00',
            'debt': '1800000.00',
        }
        mock_urlopen.return_value = self._mock_http_200(json.dumps(payload).encode('utf-8'))

        adapter = FinanSmartAdapter()
        summary = adapter.get_summary()

        self.assertIsNotNone(summary)
        self.assertEqual(summary.month, 11)
        self.assertEqual(summary.year, 2026)
        self.assertEqual(summary.currency, 'COP')
        self.assertEqual(summary.income, Decimal('3200000.00'))
        self.assertEqual(summary.expenses, Decimal('245000.00'))
        self.assertEqual(summary.balance, Decimal('2955000.00'))
        self.assertEqual(summary.savings, Decimal('1250000.00'))
        self.assertEqual(summary.debt, Decimal('1800000.00'))
        self.assertEqual(summary.source, 'FinanSmart')

        req = mock_urlopen.call_args.args[0]
        self.assertEqual(req.full_url, 'http://finansmart.local/api/v1/summary/')
        self.assertEqual(req.get_method(), 'GET')
        headers = {k.lower(): v for k, v in req.header_items()}
        self.assertEqual(headers.get('accept'), 'application/json')
        self.assertEqual(headers.get('authorization'), 'Token secret-ally-token-999')
        self.assertFalse(headers.get('authorization', '').startswith('Bearer'))
        self.assertEqual(mock_urlopen.call_args.kwargs.get('timeout'), 5)

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_http_200_allows_negative_balance(self, mock_urlopen):
        payload = {
            'month': 11,
            'year': 2026,
            'currency': 'COP',
            'income': '1200000.00',
            'expenses': '1500000.00',
            'balance': '-300000.00',
            'savings': '100000.00',
            'debt': '800000.00',
        }
        mock_urlopen.return_value = self._mock_http_200(json.dumps(payload).encode('utf-8'))

        summary = FinanSmartAdapter().get_summary()
        self.assertIsNotNone(summary)
        self.assertEqual(summary.balance, Decimal('-300000.00'))

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_http_403_invalid_token_returns_none_and_does_not_log_token(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url='http://finansmart.local/api/v1/summary/',
            code=403,
            msg='Forbidden',
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"Invalid token."}'),
        )

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING') as captured:
            summary = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary)
        combined_logs = '\n'.join(captured.output)
        self.assertNotIn('secret-ally-token-999', combined_logs)

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_http_404_not_found_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url='http://finansmart.local/api/v1/summary/',
            code=404,
            msg='Not Found',
            hdrs=None,
            fp=io.BytesIO(b'Not Found'),
        )

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            summary = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary)

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_http_500_server_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url='http://finansmart.local/api/v1/summary/',
            code=500,
            msg='Internal Server Error',
            hdrs=None,
            fp=io.BytesIO(b'Server Error'),
        )

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            summary = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary)

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_timeout_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = URLError(socket.timeout('timed out after 5s'))

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            summary = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary)

        mock_urlopen.side_effect = TimeoutError('Connection timed out')
        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            summary_direct_timeout = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary_direct_timeout)

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_invalid_json_returns_none(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_http_200(b'<<<not-valid-json>>>')

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            summary = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary)

    @patch('Volt.infra.finansmart_adapter.urlopen')
    def test_invalid_decimal_in_json_returns_none(self, mock_urlopen):
        bad_payload = {
            'month': 11,
            'year': 2026,
            'currency': 'COP',
            'income': 'monto-invalido',
            'expenses': '245000.00',
            'balance': '2955000.00',
            'savings': '1250000.00',
            'debt': '1800000.00',
        }
        mock_urlopen.return_value = self._mock_http_200(json.dumps(bad_payload).encode('utf-8'))

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            summary = FinanSmartAdapter().get_summary()

        self.assertIsNone(summary)


class FinanceCompositionRootAndViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(
        DEBUG=True,
        FINANSMART_BACKEND='',
        FINANSMART_SUMMARY_URL='',
        FINANSMART_TOKEN='',
    )
    def test_without_backend_or_credentials_even_in_debug_shows_unavailable(self):
        provider = FinanceSummaryProviderFactory.create()
        self.assertIsInstance(provider, FinanSmartAdapter)

        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            response = self.client.get('/finansmart/')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['finance_summary'])
        self.assertContains(response, 'Resumen financiero no disponible')

    @override_settings(
        DEBUG=True,
        FINANSMART_BACKEND='fake',
        FINANSMART_SUMMARY_URL='',
        FINANSMART_TOKEN='',
    )
    def test_fake_backend_shows_demo_data_with_simulated_source_label(self):
        provider = create_finance_summary_provider()
        self.assertIsInstance(provider, FakeFinanceSummaryProvider)

        response = self.client.get('/finansmart/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resumen financiero de FinanSmart')
        self.assertContains(response, 'Fuente: Datos de demostración (simulado)')
        self.assertContains(response, 'COP 3200000.00')

    def test_view_uses_injected_provider_factory_and_renders_summary(self):
        fake_provider = FakeFinanceSummaryProvider(
            summary=FinanceSummary(
                month=11,
                year=2026,
                currency='COP',
                income=Decimal('3200000.00'),
                expenses=Decimal('245000.00'),
                balance=Decimal('-150000.00'),
                savings=Decimal('1250000.00'),
                debt=Decimal('1800000.00'),
                source='FinanSmart',
            )
        )
        request = self.factory.get('/finansmart/')
        request.user = MagicMock(is_authenticated=False)

        response = finansmart_summary(request, provider_factory=lambda: fake_provider)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Resumen financiero de FinanSmart', html)
        self.assertIn('Fuente: FinanSmart', html)
        self.assertIn('COP 3200000.00', html)
        self.assertIn('COP -150000.00', html)
        self.assertIn('negative', html)
        self.assertIn('chatbot.js', html)

    def test_store_home_links_to_separate_finansmart_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/finansmart/')
        self.assertNotContains(response, 'Resumen financiero de FinanSmart')

    @override_settings(
        FINANSMART_BACKEND='remote',
        FINANSMART_SUMMARY_URL='http://finansmart.local/api/v1/summary/',
        FINANSMART_TOKEN='ultra-secret-token-never-in-html',
    )
    @patch('Volt.infra.finansmart_adapter.urlopen', side_effect=URLError('Service unreachable'))
    def test_store_and_chatbot_continue_working_when_summary_is_none(self, mock_urlopen):
        with self.assertLogs('Volt.infra.finansmart_adapter', level='WARNING'):
            response = self.client.get('/finansmart/')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['finance_summary'])
        self.assertContains(response, 'Resumen financiero de FinanSmart')
        self.assertContains(response, 'Resumen financiero no disponible')
        self.assertContains(response, 'chatbot.js')
        self.assertNotContains(response, 'ultra-secret-token-never-in-html')

        store_response = self.client.get('/')
        self.assertEqual(store_response.status_code, 200)
        self.assertContains(store_response, 'id="catalogo"')
        self.assertContains(store_response, 'store.js')
        self.assertContains(store_response, 'chatbot.js')
