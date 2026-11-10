from pathlib import Path
import tempfile
from typing import List
import unittest
from unittest.mock import patch

from app import create_app
from app.db.repositories import ProductRepository
from app.db.sqlite import init_db
from app.providers.base import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    ProviderUnavailableError,
)
from app.services.catalog_client import CatalogClientTimeoutError, FakeCatalogClient
from app.services.indexer import IndexerService
from app.services.search import SearchService
from app.tasks.indexing import (
    delete_product_task,
    reindex_catalog_task,
    upsert_product_task,
)


def _sample_product() -> dict:
    return {
        'id': 10,
        'name': 'Camisa de lino beige',
        'description': 'Manga larga fresca.',
        'price': '119900.00',
        'stock': 15,
        'color': 'beige',
        'material': 'lino',
        'gender': 'hombre',
        'available_sizes': ['S', 'M', 'L'],
        'style': 'elegante',
        'category': {'id': 2, 'name': 'Camisas', 'description': ''},
    }


class CeleryAndResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_resilience.sqlite3')
        init_db(self.db_path)
        self.repo = ProductRepository(self.db_path)
        self.catalog = FakeCatalogClient([_sample_product()])
        self.embedder = FakeEmbeddingProvider(dim=8)
        self.indexer = IndexerService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=self.embedder,
            embedding_dim=8,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_upsert_task_idempotency_embeds_only_when_semantic_text_changes(self):
        # 1. Primera ejecución: genera embedding
        res1 = upsert_product_task(10, indexer=self.indexer)
        self.assertEqual(res1['status'], 'indexed')
        self.assertEqual(len(self.embedder.embedded_documents), 1)

        # 2. Cambia solo precio y stock en Django: no re-embebe (idempotente por hash)
        p = self.catalog.get_product(10)
        p['price'] = '89900.00'
        p['stock'] = 3
        self.catalog.add_product(p)

        res2 = upsert_product_task(10, indexer=self.indexer)
        self.assertEqual(res2['status'], 'unchanged')
        self.assertEqual(len(self.embedder.embedded_documents), 1)

        # 3. Cambia color y descripción: sí re-embebe
        p['color'] = 'blanco'
        p['description'] = 'Lino italiano transpirable.'
        self.catalog.add_product(p)

        res3 = upsert_product_task(10, indexer=self.indexer)
        self.assertEqual(res3['status'], 'indexed')
        self.assertEqual(len(self.embedder.embedded_documents), 2)

    def test_delete_task_removes_product_from_index(self):
        upsert_product_task(10, indexer=self.indexer)
        self.assertIsNotNone(self.repo.get(10))

        res = delete_product_task(10, indexer=self.indexer)
        self.assertEqual(res['status'], 'deleted')
        self.assertIsNone(self.repo.get(10))

        # Segunda llamada cuando ya no existe es idempotente
        res_again = delete_product_task(10, indexer=self.indexer)
        self.assertEqual(res_again['status'], 'not_found')

    def test_upsert_task_retries_on_transient_error_and_succeeds(self):
        attempts = {'count': 0}

        class FlakyEmbedder(EmbeddingProvider):
            def embed_document(self, text: str) -> List[float]:
                attempts['count'] += 1
                if attempts['count'] < 3:
                    raise ProviderUnavailableError("Temporary 503 from Gemini")
                return [0.5] * 8

            def embed_query(self, text: str) -> List[float]:
                return [0.5] * 8

        flaky_indexer = IndexerService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=FlakyEmbedder(),
            embedding_dim=8,
        )

        res = upsert_product_task(10, indexer=flaky_indexer)
        self.assertEqual(res['status'], 'indexed')
        self.assertEqual(attempts['count'], 3)
        self.assertIsNotNone(self.repo.get(10))

    def test_upsert_task_bounded_retries_stops_after_max_retries(self):
        attempts = {'count': 0}

        class AlwaysDownCatalog:
            def get_product(self, product_id: int):
                attempts['count'] += 1
                raise CatalogClientTimeoutError("Timeout connecting to Django")

        failing_indexer = IndexerService(
            product_repo=self.repo,
            catalog_client=AlwaysDownCatalog(),
            embedding_provider=self.embedder,
            embedding_dim=8,
        )

        with self.assertRaises(CatalogClientTimeoutError):
            upsert_product_task(10, indexer=failing_indexer)

        # 1 intento inicial + 3 reintentos máximos = 4 ejecuciones totales (acotado)
        self.assertEqual(attempts['count'], 4)

    def test_stale_index_is_compensated_by_fresh_django_data_during_search(self):
        # Indexar producto con vector fijo
        self.repo.upsert(
            product_id=10,
            content_hash='initial_hash',
            embedding=[1.0, 0.0, 0.0, 0.0],
            model='gemini-embedding-001',
            dim=4,
        )

        class FixedQueryEmbedder(EmbeddingProvider):
            def embed_document(self, text: str) -> List[float]:
                return [1.0, 0.0, 0.0, 0.0]

            def embed_query(self, text: str) -> List[float]:
                return [1.0, 0.0, 0.0, 0.0]

        search_svc = SearchService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=FixedQueryEmbedder(),
            similarity_threshold=0.5,
            embedding_dim=4,
        )

        # Aunque el índice no se haya re-indexado, si en Django el stock pasa a 0, no se recomienda como disponible
        p = self.catalog.get_product(10)
        p['stock'] = 0
        self.catalog.add_product(p)

        res_agotado = search_svc.search('camisa elegante')
        self.assertEqual(res_agotado['status'], 'only_out_of_stock')
        self.assertEqual(res_agotado['products'], [])

        # Si en Django el precio sube a 250000 y el usuario filtra max_price=150000, se descarta con el dato fresco
        p['stock'] = 5
        p['price'] = '250000.00'
        self.catalog.add_product(p)

        res_caro = search_svc.search('camisa elegante', filters={'max_price': '150000'})
        self.assertEqual(res_caro['status'], 'no_results')
        self.assertEqual(res_caro['products'], [])

    def test_internal_endpoints_dispatch_celery_delay_and_handle_broker_down(self):
        app = create_app({
            'TESTING': True,
            'CHATBOT_DB_PATH': self.db_path,
            'INIT_DB_ON_STARTUP': False,
            'INTERNAL_API_KEY': 'internal-key',
        })
        client = app.test_client()
        headers = {'X-Internal-Key': 'internal-key'}

        with patch.object(upsert_product_task, 'delay') as mock_upsert_delay:
            r1 = client.post('/internal/products/sync', json={'product_id': 10, 'event': 'upserted'}, headers=headers)
            self.assertEqual(r1.status_code, 202)
            mock_upsert_delay.assert_called_once_with(10)

        with patch.object(delete_product_task, 'delay') as mock_delete_delay:
            r2 = client.post('/internal/products/sync', json={'product_id': 10, 'event': 'deleted'}, headers=headers)
            self.assertEqual(r2.status_code, 202)
            mock_delete_delay.assert_called_once_with(10)

        with patch.object(reindex_catalog_task, 'delay', side_effect=ConnectionError("Redis down")):
            r3 = client.post('/internal/reindex', json={}, headers=headers)
            self.assertEqual(r3.status_code, 503)
            self.assertEqual(r3.get_json()['error']['code'], 'queue_unavailable')


if __name__ == '__main__':
    unittest.main()
