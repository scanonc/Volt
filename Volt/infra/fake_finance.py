from decimal import Decimal
from typing import Optional

from Volt.domain.finance import FinanceSummary, FinanceSummaryProvider


class FakeFinanceSummaryProvider(FinanceSummaryProvider):
    """Proveedor fake en memoria para pruebas y desarrollo local, sin red."""

    def __init__(
        self,
        summary: Optional[FinanceSummary] = None,
        available: bool = True,
    ) -> None:
        self._available = available
        self._summary = (
            summary
            if summary is not None
            else FinanceSummary(
                month=11,
                year=2026,
                currency='COP',
                income=Decimal('6700000.00'),
                expenses=Decimal('245000.00'),
                balance=Decimal('2955000.00'),
                savings=Decimal('1250000.00'),
                debt=Decimal('1800000.00'),
                source='Datos de demostración (simulado)',
            )
        )

    def get_summary(self) -> Optional[FinanceSummary]:
        if not self._available:
            return None
        return self._summary
