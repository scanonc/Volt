from django.conf import settings

from .notifications import ConsoleNotification, EmailNotification


class NotificationFactory:
    @staticmethod
    def create():
        if settings.DEBUG:
            return ConsoleNotification()
        return EmailNotification()