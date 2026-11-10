import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand

from Volt.models import Product
from Volt.signals import send_sync_notification


class Command(BaseCommand):
    help = 'Reenvía los productos del catálogo al microservicio chatbot para reindexación.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--trigger-reindex',
            action='store_true',
            help='Dispara la tarea de reindexación en segundo plano llamando a POST /internal/reindex.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Tamaño de lote para procesar productos (por defecto 50).',
        )

    def handle(self, *args, **options):
        sync_url = getattr(settings, 'CHATBOT_SYNC_URL', '')
        if not sync_url:
            self.stderr.write(
                self.style.WARNING(
                    'CHATBOT_SYNC_URL no está configurada en settings. La sincronización HTTP está inactiva.'
                )
            )
            return

        internal_key = getattr(settings, 'CHATBOT_INTERNAL_API_KEY', '')
        timeout = getattr(settings, 'CHATBOT_SYNC_TIMEOUT', 2.0)

        # Si se solicita disparar la tarea Celery en Flask directamente
        if options.get('trigger_reindex'):
            base_url = sync_url.rsplit('/internal/', 1)[0]
            reindex_url = f"{base_url}/internal/reindex"
            headers = {'Content-Type': 'application/json'}
            if internal_key:
                headers['X-Internal-Key'] = internal_key

            req = Request(reindex_url, data=b'{}', headers=headers, method='POST')
            try:
                with urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Tarea de reindexación encolada exitosamente en Flask: {data}"
                        )
                    )
                    return
            except (HTTPError, URLError, OSError) as exc:
                self.stderr.write(
                    self.style.ERROR(f"Error al llamar a {reindex_url}: {exc}")
                )
                self.stdout.write("Procediendo a enviar eventos individuales como respaldo...")

        # Reenvío producto por producto
        products = Product.objects.all().order_by('id')
        total = products.count()
        self.stdout.write(f"Iniciando sincronización de {total} productos hacia {sync_url}...")

        success_count = 0
        error_count = 0

        for prod in products:
            try:
                send_sync_notification(prod.id, 'upserted')
                success_count += 1
            except Exception as exc:
                error_count += 1
                self.stderr.write(f"Error enviando producto {prod.id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronización finalizada. Enviados: {success_count}, Fallidos: {error_count}."
            )
        )
