from django.conf import settings

<<<<<<< HEAD
from .notifications import ConsoleNotification, EmailNotification, RemoteNotification
=======
from .notifications import ConsoleNotification, EmailNotification
>>>>>>> 616e6e1ef9f72e30884912055310c7b01b399cc3


class NotificationFactory:
    @staticmethod
    def create():
<<<<<<< HEAD
        if settings.NOTIFICATIONS_BACKEND == 'remote':
            return RemoteNotification()
        if settings.DEBUG:
            return ConsoleNotification()
        return EmailNotification()
=======
        if settings.DEBUG:
            return ConsoleNotification()
        return EmailNotification()
>>>>>>> 616e6e1ef9f72e30884912055310c7b01b399cc3
