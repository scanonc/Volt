import logging
from typing import Any, Dict, Optional

from app.config import Config
from app.db.repositories import ProductRepository
from app.db.sqlite import init_db
from app.providers.base import ProviderError
from app.providers.gemini import GeminiEmbeddingAdapter
from app.services.catalog_client import CatalogClient, CatalogClientError
from app.services.indexer import IndexerService
from .celery_app import celery_app

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (CatalogClientError, ProviderError)


def build_default_indexer() -> IndexerService:
    """Construye una instancia de IndexerService con la configuración por defecto."""
    init_db(Config.CHATBOT_DB_PATH)
    product_repo = ProductRepository(Config.CHATBOT_DB_PATH)
    catalog_client = CatalogClient(
        base_url=Config.DJANGO_BASE_URL,
        timeout=Config.DJANGO_TIMEOUT,
    )
    embedding_provider = GeminiEmbeddingAdapter(
        api_key=Config.GEMINI_API_KEY,
        model=Config.GEMINI_EMBEDDING_MODEL,
        dim=Config.EMBEDDING_DIM,
    )
    return IndexerService(
        product_repo=product_repo,
        catalog_client=catalog_client,
        embedding_provider=embedding_provider,
        embedding_model=Config.GEMINI_EMBEDDING_MODEL,
        embedding_dim=Config.EMBEDDING_DIM,
    )


@celery_app.task(
    name='chatbot.upsert_product',
    autoretry_for=RETRYABLE_ERRORS,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
)
def upsert_product_task(
    product_id: int,
    indexer: Optional[IndexerService] = None,
) -> Dict[str, Any]:
    """Tarea Celery idempotente para crear o actualizar el embedding de un producto."""
    svc = indexer or build_default_indexer()
    pid = int(product_id)
    try:
        status = svc.upsert_product(pid)
        logger.info("Tarea upsert_product completada para product_id=%d: status=%s", pid, status)
        return {'product_id': pid, 'event': 'upserted', 'status': status}
    except Exception as exc:
        logger.error("Fallo en upsert_product para product_id=%d: %s", pid, exc)
        raise


@celery_app.task(
    name='chatbot.delete_product',
    autoretry_for=RETRYABLE_ERRORS,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
)
def delete_product_task(
    product_id: int,
    indexer: Optional[IndexerService] = None,
) -> Dict[str, Any]:
    """Tarea Celery para eliminar un producto del índice SQLite."""
    svc = indexer or build_default_indexer()
    pid = int(product_id)
    try:
        removed = svc.delete_product(pid)
        status = 'deleted' if removed else 'not_found'
        logger.info("Tarea delete_product completada para product_id=%d: status=%s", pid, status)
        return {'product_id': pid, 'event': 'deleted', 'status': status}
    except Exception as exc:
        logger.error("Fallo en delete_product para product_id=%d: %s", pid, exc)
        raise


@celery_app.task(
    name='chatbot.sync_product',
    autoretry_for=RETRYABLE_ERRORS,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
)
def sync_product_task(
    product_id: int,
    event: str = 'upserted',
    indexer: Optional[IndexerService] = None,
) -> Dict[str, Any]:
    """Tarea Celery unificada que despacha upsert o delete según el evento recibido desde Django."""
    svc = indexer or build_default_indexer()
    pid = int(product_id)

    try:
        if event == 'deleted':
            removed = svc.delete_product(pid)
            status = 'deleted' if removed else 'not_found'
            logger.info("Sincronización (deleted) completada para product_id=%d: %s", pid, status)
            return {'product_id': pid, 'event': event, 'status': status}

        if event == 'upserted':
            status = svc.upsert_product(pid)
            logger.info("Sincronización (upserted) completada para product_id=%d: %s", pid, status)
            return {'product_id': pid, 'event': event, 'status': status}
    except Exception as exc:
        logger.error("Fallo en sync_product para product_id=%d (%s): %s", pid, event, exc)
        raise

    raise ValueError(f"Evento de sincronización no soportado: {event}")


@celery_app.task(
    name='chatbot.reindex_catalog',
    autoretry_for=RETRYABLE_ERRORS,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
)
def reindex_catalog_task(
    page_size: int = 50,
    indexer: Optional[IndexerService] = None,
) -> Dict[str, int]:
    """Tarea Celery para reindexación inicial o completa del catálogo con limpieza de obsoletos."""
    svc = indexer or build_default_indexer()
    try:
        summary = svc.reindex_catalog(page_size=page_size)
        logger.info("Reindexación de catálogo completada: %s", summary)
        return summary
    except Exception as exc:
        logger.error("Fallo en reindex_catalog: %s", exc)
        raise
