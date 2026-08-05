class BaseNotification:
    def send_confirmation(self, order):
        raise NotImplementedError('Subclasses must implement send_confirmation().')


class ConsoleNotification(BaseNotification):
    def send_confirmation(self, order):
        print(f'Pedido #{order.id} confirmado para {order.user.username}')


class EmailNotification(BaseNotification):
    def send_confirmation(self, order):
        print(f'Correo de confirmación enviado para pedido #{order.id}')
