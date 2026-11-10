import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Product

logger = logging.getLogger(__name__)


def send_sync_notification(product_id: int, event: str) -> None:
    """Envía un evento HTTP mínimo a Flask para sincronización del catálogo."""
    sync_url = getattr(settings, 'CHATBOT_SYNC_URL', '')
    if not sync_url:
        return

    internal_key = getattr(settings, 'CHATBOT_INTERNAL_API_KEY', '')
    timeout = getattr(settings, 'CHATBOT_SYNC_TIMEOUT', 2.0)

    payload = json.dumps({'product_id': product_id, 'event': event}).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if internal_key:
        headers['X-Internal-Key'] = internal_key

    req = Request(sync_url, data=payload, headers=headers, method='POST')
    try:
        with urlopen(req, timeout=timeout) as resp:
            logger.info(
                "Notificación de producto %s (%s) enviada al chatbot: status %s",
                product_id,
                event,
                resp.status,
            )
    except (HTTPError, URLError, OSError, Exception) as exc:
        logger.warning(
            "Fallo al enviar notificación al chatbot en %s para producto %s (%s): %s",
            sync_url,
            product_id,
            event,
            exc,
        )


@receiver(post_save, sender=Product)
def product_post_save_handler(sender, instance, created, update_fields=None, **kwargs):
    """Notifica cambios en producto a Flask, ignorando actualizaciones que solo tocan stock o precio."""
    if not created and update_fields is not None:
        updated_set = set(update_fields)
        if updated_set and updated_set.issubset({'stock', 'price'}):
            logger.debug(
                "Omitiendo notificación a chatbot para producto %s: solo cambió %s",
                instance.id,
                updated_set,
            )
            return

    pid = instance.id
    transaction.on_commit(lambda: send_sync_notification(pid, 'upserted'))


@receiver(post_delete, sender=Product)
def product_post_delete_handler(sender, instance, **kwargs):
    """Notifica la eliminación de un producto a Flask."""
    pid = instance.id
    transaction.on_commit(lambda: send_sync_notification(pid, 'deleted'))
