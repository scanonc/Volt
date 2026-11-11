import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import JsonResponse


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
