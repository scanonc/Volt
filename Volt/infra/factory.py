from django.conf import settings

from .notifications import ConsoleNotification, EmailNotification, RemoteNotification


class NotificationFactory:
    @staticmethod
    def create():
        if settings.NOTIFICATIONS_BACKEND == 'remote':
            return RemoteNotification()
        if settings.DEBUG:
            return ConsoleNotification()
        return EmailNotification()
