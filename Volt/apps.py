from django.apps import AppConfig


class VoltConfig(AppConfig):
    name = 'Volt'

    def ready(self):
        import Volt.signals  # noqa: F401
