class BaseNotification:
    def send_confirmation(self, order):
        raise NotImplementedError('Subclasses must implement send_confirmation().')


class ConsoleNotification(BaseNotification):
    def send_confirmation(self, order):
        print(f'Pedido #{order.id} confirmado para {order.user.username}')


class EmailNotification(BaseNotification):
    def send_confirmation(self, order):
        print(f'Correo de confirmación enviado para pedido #{order.id}')


class RemoteNotification(BaseNotification):
    """Adaptador HTTP con tiempo límite; el fallo no invalida un pedido confirmado."""
    def send_confirmation(self, order):
        import json
        import logging
        from urllib.error import URLError
        from urllib.request import Request, urlopen
        from django.conf import settings

        payload = json.dumps({
            'order_id': order.id,
            'username': order.user.username,
            'channel': 'console' if settings.DEBUG else 'email',
        }).encode('utf-8')
        request = Request(settings.NOTIFICATIONS_URL, data=payload, method='POST', headers={
            'Content-Type': 'application/json',
            'X-API-Key': settings.NOTIFICATIONS_API_KEY,
        })
        try:
            with urlopen(request, timeout=settings.NOTIFICATIONS_TIMEOUT) as response:
                result = json.loads(response.read())
                if not isinstance(result, dict) or result.get('status') != 'simulated':
                    raise ValueError('Respuesta inesperada del servicio de notificaciones')
                return result
        except (URLError, OSError, ValueError):
            logging.getLogger(__name__).exception(
                'No se pudo notificar el pedido %s; el pedido permanece confirmado.', order.id)
            return None
