import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
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


def notification_health(request):
    health_url = settings.NOTIFICATIONS_URL.replace('/api/v2/notifications/', '/health/')
    try:
        with urlopen(health_url, timeout=2) as response:
            return JsonResponse(json.loads(response.read()), status=response.status)
    except (HTTPError, URLError, OSError, ValueError):
        return JsonResponse({'status': 'offline', 'service': 'notifications'}, status=503)


def send_notification(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({'error': {'message': 'JSON inválido.'}}, status=400)

    try:
        api_request = Request(
            settings.NOTIFICATIONS_URL,
            data=json.dumps(payload).encode('utf-8'),
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': settings.NOTIFICATIONS_API_KEY,
            },
        )
        with urlopen(api_request, timeout=settings.NOTIFICATIONS_TIMEOUT) as response:
            return JsonResponse(json.loads(response.read()), status=response.status)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read())
        except (TypeError, ValueError):
            error = {'error': {'message': 'El servicio rechazó la solicitud.'}}
        return JsonResponse(error, status=exc.code)
    except (URLError, OSError, ValueError):
        return JsonResponse(
            {'error': {'message': 'El servicio de notificaciones no está disponible.'}},
            status=503,
        )
