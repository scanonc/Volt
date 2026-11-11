from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render


def store_home(request):
    return render(request, 'store/index.html')


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
