from decimal import Decimal, InvalidOperation
import json
import logging
import socket
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from Volt.domain.finance import FinanceSummary, FinanceSummaryProvider

logger = logging.getLogger(__name__)


class FinanSmartAdapter(FinanceSummaryProvider):
    """Adaptador HTTP para consumir el endpoint /api/v1/summary/ de FinanSmart.

    Es el único componente del sistema que conoce el formato HTTP/JSON,
    los encabezados de autenticación (Token) y los campos del servicio aliado.
    """

    DEFAULT_TIMEOUT = 5

    def __init__(
        self,
        summary_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.summary_url = (
            summary_url
            if summary_url is not None
            else getattr(settings, 'FINANSMART_SUMMARY_URL', '')
        )
        self.token = (
            token
            if token is not None
            else getattr(settings, 'FINANSMART_TOKEN', '')
        )
        self.timeout = timeout

    @staticmethod
    def _parse_decimal(raw_value: Any) -> Decimal:
        if isinstance(raw_value, bool) or raw_value is None:
            raise ValueError('Valor decimal inválido')
        if not isinstance(raw_value, (str, int, Decimal)):
            raise ValueError('Se esperaba cadena decimal')
        value = Decimal(str(raw_value).strip())
        if not value.is_finite():
            raise ValueError('Valor decimal no finito')
        return value

    @staticmethod
    def _parse_int(raw_value: Any) -> int:
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError('Se esperaba entero exacto')
        return raw_value

    def get_summary(self) -> Optional[FinanceSummary]:
        if not self.summary_url or not self.token:
            logger.warning(
                'FinanSmartAdapter no configurado: falta FINANSMART_SUMMARY_URL o FINANSMART_TOKEN.'
            )
            return None

        request = Request(
            self.summary_url,
            method='GET',
            headers={
                'Accept': 'application/json',
                'Authorization': f'Token {self.token}',
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                status_code = getattr(response, 'status', 200)
                if status_code != 200:
                    logger.warning(
                        'FinanSmart respondió con código inesperado: %s',
                        status_code,
                    )
                    return None
                raw_body = response.read()
        except HTTPError as exc:
            logger.warning(
                'Error HTTP al consultar FinanSmart (status %s).',
                exc.code,
            )
            return None
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            logger.warning(
                'Error de red o timeout al consultar FinanSmart (%s).',
                type(exc).__name__,
            )
            return None

        try:
            if isinstance(raw_body, bytes):
                raw_body = raw_body.decode('utf-8')
            payload = json.loads(raw_body)
            if not isinstance(payload, dict):
                raise ValueError('El JSON de FinanSmart debe ser un objeto')

            month = self._parse_int(payload['month'])
            year = self._parse_int(payload['year'])
            if not 1 <= month <= 12:
                raise ValueError('Mes fuera de rango')

            currency = payload['currency']
            if not isinstance(currency, str) or not currency.strip():
                raise ValueError('Moneda inválida')

            return FinanceSummary(
                month=month,
                year=year,
                currency=currency.strip(),
                income=self._parse_decimal(payload['income']),
                expenses=self._parse_decimal(payload['expenses']),
                balance=self._parse_decimal(payload['balance']),
                savings=self._parse_decimal(payload['savings']),
                debt=self._parse_decimal(payload['debt']),
                source='FinanSmart',
            )
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            UnicodeDecodeError,
        ) as exc:
            logger.warning(
                'Respuesta inválida de FinanSmart (%s).',
                type(exc).__name__,
            )
            return None
