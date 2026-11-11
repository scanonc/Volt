from typing import Callable, Optional

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render

from .domain.finance import FinanceSummaryProvider
from .infra.factory import create_finance_summary_provider


def store_home(request):
    return render(request, 'store/index.html')


def finansmart_summary(
    request,
    finance_provider: Optional[FinanceSummaryProvider] = None,
    provider_factory: Callable[[], FinanceSummaryProvider] = create_finance_summary_provider,
):
    provider = finance_provider if finance_provider is not None else provider_factory()
    finance_summary = provider.get_summary()
    return render(
        request,
        'store/finansmart.html',
        {
            'finance_summary': finance_summary,
        },
    )


def register(request):
    """Registro de compradores con el formulario estándar de Django (solo presentación)."""
    if request.user.is_authenticated:
        return redirect('store')
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('store')
    return render(request, 'store/register.html', {'form': form})


def notification_dashboard(request):
    return render(request, 'dashboard/index.html', {'csrf_token': get_token(request)})
