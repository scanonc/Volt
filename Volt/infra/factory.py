from django.conf import settings

from Volt.domain.finance import FinanceSummaryProvider

from .fake_finance import FakeFinanceSummaryProvider
from .finansmart_adapter import FinanSmartAdapter
from .notifications import ConsoleNotification, EmailNotification, RemoteNotification


class NotificationFactory:
    @staticmethod
    def create():
        if settings.NOTIFICATIONS_BACKEND == 'remote':
            return RemoteNotification()
        if settings.DEBUG:
            return ConsoleNotification()
        return EmailNotification()


class FinanceSummaryProviderFactory:
    """Composition root que resuelve el proveedor de resumen financiero (DIP)."""

    @staticmethod
    def create() -> FinanceSummaryProvider:
        backend = getattr(settings, 'FINANSMART_BACKEND', '').strip().lower()
        if backend == 'fake':
            return FakeFinanceSummaryProvider()

        summary_url = getattr(settings, 'FINANSMART_SUMMARY_URL', '')
        token = getattr(settings, 'FINANSMART_TOKEN', '')
        timeout = getattr(settings, 'FINANSMART_TIMEOUT', FinanSmartAdapter.DEFAULT_TIMEOUT)
        return FinanSmartAdapter(
            summary_url=summary_url,
            token=token,
            timeout=timeout,
        )


def create_finance_summary_provider() -> FinanceSummaryProvider:
    """Fábrica funcional para inyectar FinanceSummaryProvider en las vistas."""
    return FinanceSummaryProviderFactory.create()
