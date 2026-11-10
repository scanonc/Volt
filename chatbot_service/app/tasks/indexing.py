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
    name='chatbot.sync_product',
    autoretry_for=(CatalogClientError, ProviderError),
    max_retries=3,
    retry_backoff=True,
)
def sync_product_task(
    product_id: int,
    event: str = 'upserted',
    indexer: Optional[IndexerService] = None,
) -> Dict[str, Any]:
    """Tarea envoltorio delgado de Celery para sincronizar un producto individual."""
    svc = indexer or build_default_indexer()
    pid = int(product_id)

    if event == 'deleted':
        removed = svc.delete_product(pid)
        return {'product_id': pid, 'event': event, 'status': 'deleted' if removed else 'not_found'}

    if event == 'upserted':
        status = svc.upsert_product(pid)
        return {'product_id': pid, 'event': event, 'status': status}

    raise ValueError(f"Evento de sincronización no soportado: {event}")


@celery_app.task(
    name='chatbot.reindex_catalog',
    autoretry_for=(CatalogClientError, ProviderError),
    max_retries=3,
    retry_backoff=True,
)
def reindex_catalog_task(
    page_size: int = 50,
    indexer: Optional[IndexerService] = None,
) -> Dict[str, int]:
    """Tarea envoltorio delgado de Celery para reindexación inicial o completa del catálogo."""
    svc = indexer or build_default_indexer()
    return svc.reindex_catalog(page_size=page_size)
