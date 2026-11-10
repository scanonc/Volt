import hmac
from flask import Blueprint, current_app, jsonify, request

from app.tasks.indexing import reindex_catalog_task, sync_product_task

internal_bp = Blueprint('internal', __name__, url_prefix='/internal')


def _verify_internal_key():
    """Valida el header X-Internal-Key si INTERNAL_API_KEY está configurado."""
    expected_key = current_app.config.get('INTERNAL_API_KEY', '')
    if not expected_key:
        return None

    provided_key = request.headers.get('X-Internal-Key', '')
    if not hmac.compare_digest(provided_key, expected_key):
        return jsonify(error={
            'code': 'unauthorized',
            'message': 'Clave interna inválida o ausente.',
        }), 401
    return None


@internal_bp.post('/products/sync', strict_slashes=False)
def sync_product():
    """Endpoint interno para recibir eventos post_save/post_delete desde Django y encolarlos en Celery."""
    auth_error = _verify_internal_key()
    if auth_error is not None:
        return auth_error

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error={
            'code': 'invalid_json',
            'message': 'Se requiere un objeto JSON válido.',
        }), 400

    product_id = data.get('product_id')
    event = data.get('event')

    if type(product_id) is not int or product_id <= 0 or event not in ('upserted', 'deleted'):
        return jsonify(error={
            'code': 'invalid_payload',
            'message': 'product_id debe ser un entero positivo y event debe ser "upserted" o "deleted".',
        }), 400

    try:
        enqueuer = current_app.config.get('SYNC_TASK_ENQUEUER')
        if callable(enqueuer):
            enqueuer(product_id, event)
        else:
            sync_product_task.delay(product_id, event)
    except Exception as exc:
        current_app.logger.error("No se pudo encolar la tarea de sincronización en Redis/Celery: %s", exc)
        return jsonify(error={
            'code': 'queue_unavailable',
            'message': 'El servicio de cola de tareas no está disponible temporalmente.',
        }), 503

    return jsonify(status='queued', product_id=product_id, event=event), 202


@internal_bp.post('/reindex', strict_slashes=False)
def trigger_reindex():
    """Endpoint interno para disparar la reindexación completa del catálogo en segundo plano."""
    auth_error = _verify_internal_key()
    if auth_error is not None:
        return auth_error

    try:
        reindex_catalog_task.delay()
    except Exception as exc:
        current_app.logger.error("No se pudo encolar la tarea de reindexación en Redis/Celery: %s", exc)
        return jsonify(error={
            'code': 'queue_unavailable',
            'message': 'El servicio de cola de tareas no está disponible temporalmente.',
        }), 503

    return jsonify(status='queued'), 202
