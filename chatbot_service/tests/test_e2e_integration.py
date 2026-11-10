from decimal import Decimal
import json
from pathlib import Path
import tempfile
from typing import Dict, List
import unittest

from app import create_app
from app.db.repositories import ConversationRepository, ProductRepository
from app.db.sqlite import init_db
from app.providers.base import EmbeddingProvider, FakeTextGenerator
from app.services.catalog_client import FakeCatalogClient
from app.services.chat import ChatService
from app.services.indexer import IndexerService
from app.services.search import SearchService


class ControlledEmbeddingProvider(EmbeddingProvider):
    """Proveedor determinista para pruebas de integración con vectores normalizados."""

    def __init__(self, mapping: Dict[str, List[float]], default_vec: List[float]):
        self.mapping = mapping
        self.default_vec = default_vec

    def _resolve(self, text: str) -> List[float]:
        for key, vec in self.mapping.items():
            if key.lower() in text.lower():
                return list(vec)
        return list(self.default_vec)

    def embed_document(self, text: str) -> List[float]:
        return self._resolve(text)

    def embed_query(self, text: str) -> List[float]:
        return self._resolve(text)


class EndToEndIntegrationTests(unittest.TestCase):
    """Pruebas de integración del flujo completo Django <-> Flask."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_e2e.sqlite3')
        init_db(self.db_path)

        self.product_repo = ProductRepository(self.db_path)
        self.conv_repo = ConversationRepository(self.db_path)

        # Simula el catálogo de Django con los campos reales
        self.django_catalog = FakeCatalogClient([
            {
                'id': 101,
                'name': 'Pantalón Cargo Urbano',
                'description': 'Bolsillos laterales en algodón resistente.',
                'price': '139900.00',
                'stock': 12,
                'color': 'verde',
                'material': 'algodón',
                'gender': 'hombre',
                'available_sizes': ['M', 'L'],
                'style': 'urbano',
                'category': {'id': 3, 'name': 'Pantalones', 'description': ''},
            },
            {
                'id': 102,
                'name': 'Vestido Floral de Fiesta',
                'description': 'Elegante y fresco para eventos nocturnos.',
                'price': '149900.00',
                'stock': 8,
                'color': 'rojo',
                'material': 'seda',
                'gender': 'mujer',
                'available_sizes': ['S', 'M'],
                'style': 'elegante',
                'category': {'id': 5, 'name': 'Vestidos', 'description': ''},
            },
        ])

        self.embedder = ControlledEmbeddingProvider(
            mapping={
                'Pantalón Cargo Urbano': [1.0, 0.0, 0.0, 0.0],
                'Vestido Floral de Fiesta': [0.0, 1.0, 0.0, 0.0],
                'pantalon comodo urbano': [1.0, 0.0, 0.0, 0.0],
                'vestido fiesta elegante': [0.0, 1.0, 0.0, 0.0],
            },
            default_vec=[0.5, 0.5, 0.5, 0.5],
        )

        self.indexer = IndexerService(
            product_repo=self.product_repo,
            catalog_client=self.django_catalog,
            embedding_provider=self.embedder,
            embedding_dim=4,
        )
        # Reindexación inicial
        self.indexer.reindex_catalog()

        self.search_service = SearchService(
            product_repo=self.product_repo,
            catalog_client=self.django_catalog,
            embedding_provider=self.embedder,
            similarity_threshold=0.55,
            top_k=5,
            max_results=3,
            embedding_dim=4,
        )

        self.text_gen = FakeTextGenerator()
        self.chat_service = ChatService(
            conversation_repo=self.conv_repo,
            search_service=self.search_service,
            text_generator=self.text_gen,
        )

        self.app = create_app({
            'TESTING': True,
            'CHATBOT_DB_PATH': self.db_path,
            'INIT_DB_ON_STARTUP': False,
            'INTERNAL_API_KEY': 'internal-e2e-secret',
            'CHAT_SERVICE': self.chat_service,
            'PRODUCT_REPO': self.product_repo,
            'CONVERSATION_REPO': self.conv_repo,
            'CATALOG_CLIENT': self.django_catalog,
            'EMBEDDING_PROVIDER': self.embedder,
            'TEXT_GENERATOR': self.text_gen,
            'SEARCH_SERVICE': self.search_service,
            'EMBEDDING_DIM': 4,
            'SYNC_TASK_ENQUEUER': lambda pid, ev: (
                self.indexer.upsert_product(pid) if ev == 'upserted' else self.indexer.delete_product(pid)
            ),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_lifecycle_create_sync_chat_price_change_delete(self):
        headers = {'X-Internal-Key': 'internal-e2e-secret'}

        # 1. Django notifica nuevo producto vía POST /internal/products/sync
        self.django_catalog.add_product({
            'id': 103,
            'name': 'Chaqueta Impermeable Cortavientos',
            'description': 'Ideal para lluvia ligera y clima frío.',
            'price': '189900.00',
            'stock': 10,
            'color': 'azul',
            'material': 'nylon',
            'gender': 'unisex',
            'available_sizes': ['M', 'L', 'XL'],
            'style': 'deportivo',
            'category': {'id': 7, 'name': 'Chaquetas', 'description': ''},
        })
        self.embedder.mapping['Chaqueta Impermeable Cortavientos'] = [0.0, 0.0, 1.0, 0.0]
        self.embedder.mapping['chaqueta lluvia azul'] = [0.0, 0.0, 1.0, 0.0]

        sync_resp = self.client.post(
            '/internal/products/sync',
            json={'product_id': 103, 'event': 'upserted'},
            headers=headers,
        )
        self.assertEqual(sync_resp.status_code, 202)
        self.assertIsNotNone(self.product_repo.get(103))

        # 2. Chat consulta y recomienda el producto indexado con datos frescos
        self.text_gen.queue_response(json.dumps({
            'search_text': 'chaqueta lluvia azul',
            'color': 'azul',
            'style': 'deportivo',
        }))
        self.text_gen.queue_response("Te recomiendo la Chaqueta Impermeable Cortavientos azul.")

        chat_resp = self.client.post('/api/chatbot/message/', json={
            'message': 'Busco una chaqueta deportiva azul para la lluvia',
        })
        self.assertEqual(chat_resp.status_code, 200)
        chat_data = chat_resp.get_json()
        self.assertEqual(len(chat_data['products']), 1)
        self.assertEqual(chat_data['products'][0]['id'], 103)
        self.assertEqual(chat_data['products'][0]['stock'], 10)
        self.assertEqual(chat_data['products'][0]['price'], '189900.00')

        # 3. Cambio de precio y stock en Django: el índice no re-embee, pero la búsqueda usa el precio fresco
        prod = self.django_catalog.get_product(103)
        prod['price'] = '210000.00'
        prod['stock'] = 3
        self.django_catalog.add_product(prod)

        # Chat con filtro estricto max_price=200000 -> debe ser descartado por el precio fresco
        self.text_gen.queue_response(json.dumps({
            'search_text': 'chaqueta lluvia azul',
            'max_price': 200000,
        }))
        self.text_gen.queue_response("No encontré chaquetas por menos de 200 mil pesos.")

        chat_resp2 = self.client.post('/api/chatbot/message/', json={
            'message': 'Busco chaqueta para lluvia de máximo 200 mil',
        })
        self.assertEqual(chat_resp2.status_code, 200)
        self.assertEqual(chat_resp2.get_json()['products'], [])

        # 4. Eliminación en Django y notificación
        self.django_catalog.remove_product(103)
        del_resp = self.client.post(
            '/internal/products/sync',
            json={'product_id': 103, 'event': 'deleted'},
            headers=headers,
        )
        self.assertEqual(del_resp.status_code, 202)
        self.assertIsNone(self.product_repo.get(103))


if __name__ == '__main__':
    unittest.main()
