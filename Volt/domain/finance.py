from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class FinanceSummary:
    """Resumen financiero general proveniente de un proveedor externo.

    Nota de dominio: representa el estado financiero general del usuario
    (ingresos, gastos, balance, ahorros y deuda) y no constituye un
    presupuesto exclusivo para compra de ropa.
    """

    month: int
    year: int
    currency: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    savings: Decimal
    debt: Decimal
    source: str = 'FinanSmart'


class FinanceSummaryProvider(ABC):
    """Puerto (interfaz abstracta) para consultar el resumen financiero (DIP)."""

    @abstractmethod
    def get_summary(self) -> Optional[FinanceSummary]:
        """Devuelve un FinanceSummary o None si el servicio no está disponible."""
        raise NotImplementedError
