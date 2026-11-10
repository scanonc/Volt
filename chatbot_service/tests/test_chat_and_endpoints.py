import json
from pathlib import Path
import tempfile
from typing import Dict, List
import unittest

from app import create_app
from app.db.repositories import ConversationRepository, ProductRepository
from app.db.sqlite import init_db
from app.providers.base import (
    EmbeddingProvider,
    FakeTextGenerator,
    ProviderQuotaError,
    TextGenerator,
)
from app.services.catalog_client import CatalogClientUnavailableError, FakeCatalogClient
from app.services.chat import ChatService
from app.services.indexer import IndexerService
from app.services.search import SearchService


class ControlledEmbeddingProvider(EmbeddingProvider):
    """Proveedor de embeddings controlado para pruebas deterministas de flujo RAG."""

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


def _sample_catalog() -> List[dict]:
    return [
        {
            'id': 11,
            'name': 'Short deportivo azul [DEMO]',
            'description': 'Secado rápido para clima cálido.',
            'price': '49900.00',
            'stock': 20,
            'color': 'azul',
            'material': 'poliéster',
            'gender': 'unisex',
            'available_sizes': ['M', 'L'],
            'style': 'deportivo',
            'category': {'id': 6, 'name': 'Ropa deportiva', 'description': ''},
        },
        {
            'id': 12,
            'name': 'Camiseta básica blanca [DEMO]',
            'description': 'Algodón ligero.',
            'price': '39900.00',
            'stock': 15,
            'color': 'blanco',
            'material': 'algodón',
            'gender': 'unisex',
            'available_sizes': ['S', 'M', 'L'],
            'style': 'casual',
            'category': {'id': 1, 'name': 'Camisetas', 'description': ''},
        },
    ]


class ChatAndEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_chat.sqlite3')
        init_db(self.db_path)

        self.product_repo = ProductRepository(self.db_path)
        self.conv_repo = ConversationRepository(self.db_path)
        self.catalog = FakeCatalogClient(_sample_catalog())

        self.embedder = ControlledEmbeddingProvider(
            mapping={
                'Short deportivo azul': [1.0, 0.0, 0.0, 0.0],
                'Camiseta básica blanca': [0.8, 0.6, 0.0, 0.0],
                'ropa deportiva calor': [1.0, 0.0, 0.0, 0.0],
                'algo inexistente nieve': [-1.0, 0.0, 0.0, 0.0],
            },
            default_vec=[1.0, 0.0, 0.0, 0.0],
        )

        self.indexer = IndexerService(
            product_repo=self.product_repo,
            catalog_client=self.catalog,
            embedding_provider=self.embedder,
            embedding_dim=4,
        )
        self.indexer.reindex_catalog()

        self.search_service = SearchService(
            product_repo=self.product_repo,
            catalog_client=self.catalog,
            embedding_provider=self.embedder,
            similarity_threshold=0.55,
            top_k=10,
            max_results=4,
            embedding_dim=4,
        )

        self.text_gen = FakeTextGenerator(
            default_response="Te sugiero estas opciones reales del catálogo de Volt."
        )

        self.chat_service = ChatService(
            conversation_repo=self.conv_repo,
            search_service=self.search_service,
            text_generator=self.text_gen,
            history_limit=6,
        )

        self.app = create_app({
            'TESTING': True,
            'CHATBOT_DB_PATH': self.db_path,
            'INIT_DB_ON_STARTUP': False,
            'INTERNAL_API_KEY': 'secret-internal-key',
            'CHAT_SERVICE': self.chat_service,
            'PRODUCT_REPO': self.product_repo,
            'CONVERSATION_REPO': self.conv_repo,
            'CATALOG_CLIENT': self.catalog,
            'EMBEDDING_PROVIDER': self.embedder,
            'TEXT_GENERATOR': self.text_gen,
            'SEARCH_SERVICE': self.search_service,
            'EMBEDDING_DIM': 4,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_conversation_and_query_with_results(self):
        # 1a llamada a TextGenerator: extracción de JSON; 2a llamada: redacción de respuesta
        self.text_gen.queue_response(json.dumps({
            'search_text': 'ropa deportiva calor',
            'max_price': 60000,
            'color': 'azul',
            'style': 'deportivo',
        }))
        self.text_gen.queue_response("Te recomiendo el Short deportivo azul [DEMO] por $49900.00 COP.")

        resp = self.client.post('/api/chatbot/message/', json={
            'message': 'Busco ropa deportiva azul para el calor, máximo 60 mil',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('conversation_id', data)
        self.assertTrue(len(data['conversation_id']) > 0)
        self.assertIn('Short deportivo azul', data['reply'])
        self.assertEqual(len(data['products']), 1)

        product = data['products'][0]
        self.assertEqual(product['id'], 11)
        self.assertEqual(product['color'], 'azul')
        self.assertEqual(product['style'], 'deportivo')
        self.assertEqual(product['available_sizes'], ['M', 'L'])
        self.assertNotIn('similarity_score', product)

        # Verificar que se guardaron los 2 mensajes (user y assistant) en SQLite
        conv = self.conv_repo.get_conversation(data['conversation_id'])
        messages = self.conv_repo.get_recent_messages(conv['id'])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertEqual(messages[1]['role'], 'assistant')

    def test_existing_conversation_loads_history_and_invalid_json_falls_back_gracefully(self):
        conv = self.conv_repo.create_conversation(session_id='conv-existente-123')
        self.conv_repo.add_message(conv['id'], 'user', 'Hola, busco camisetas.')
        self.conv_repo.add_message(conv['id'], 'assistant', '¡Hola! ¿De qué color o talla buscas?')

        # Simular que el LLM devuelve texto no JSON en el paso de extracción: debe continuar sin filtros
        self.text_gen.queue_response("Esto no es un JSON válido {{{")
        self.text_gen.queue_response("Aquí tienes nuestras opciones disponibles.")

        resp = self.client.post('/api/chatbot/message/', json={
            'conversation_id': 'conv-existente-123',
            'message': 'Muéstrame cualquiera disponible',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['conversation_id'], 'conv-existente-123')
        self.assertEqual(len(data['products']), 2)

        # Verificar que el historial previo se incluyó en el prompt enviado al generador
        self.assertIn('Hola, busco camisetas.', self.text_gen.calls[0]['prompt'])

        # Ahora la conversación tiene 4 mensajes
        messages = self.conv_repo.get_recent_messages(conv['id'])
        self.assertEqual(len(messages), 4)

    def test_nonexistent_conversation_id_returns_404(self):
        resp = self.client.post('/api/chatbot/message/', json={
            'conversation_id': 'id-que-no-existe',
            'message': 'Hola',
        })
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data['error']['code'], 'conversation_not_found')

    def test_query_without_results_returns_empty_products_list(self):
        self.text_gen.queue_response(json.dumps({
            'search_text': 'algo inexistente nieve',
            'color': None,
        }))
        self.text_gen.queue_response(
            "No encontré prendas disponibles en el catálogo para nieve. ¿Buscas otro tipo de prenda?"
        )

        resp = self.client.post('/api/chatbot/message/', json={
            'message': 'Busco un traje térmico para nieve extrema',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['products'], [])
        self.assertIn('No encontré prendas', data['reply'])
        # Verificar que el prompt RAG informó que no hubo productos disponibles
        rag_prompt = self.text_gen.calls[1]['prompt']
        self.assertIn('Ningún producto disponible cumple los criterios', rag_prompt)

    def test_validation_400_on_empty_or_too_long_message(self):
        # Mensaje vacío
        r1 = self.client.post('/api/chatbot/message/', json={'message': '   '})
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.get_json()['error']['code'], 'invalid_payload')

        # Sin campo message
        r2 = self.client.post('/api/chatbot/message/', json={})
        self.assertEqual(r2.status_code, 400)

        # Mensaje que excede longitud máxima (1000 chars)
        r3 = self.client.post('/api/chatbot/message/', json={'message': 'a' * 1005})
        self.assertEqual(r3.status_code, 400)

        # conversation_id inválido (entero booleano o vacío)
        r4 = self.client.post('/api/chatbot/message/', json={'message': 'Hola', 'conversation_id': '  '})
        self.assertEqual(r4.status_code, 400)

    def test_ai_provider_error_returns_controlled_503(self):
        class FailingTextGenerator(TextGenerator):
            def generate(self, prompt: str, system_instruction=None) -> str:
                raise ProviderQuotaError("Quota exceeded for project 123456")

        self.app.config['CHAT_SERVICE'] = ChatService(
            conversation_repo=self.conv_repo,
            search_service=self.search_service,
            text_generator=FailingTextGenerator(),
        )

        resp = self.client.post('/api/chatbot/message/', json={'message': 'Hola'})
        self.assertEqual(resp.status_code, 503)
        data = resp.get_json()
        self.assertEqual(data['error']['code'], 'llm_unavailable')
        # No debe filtrar detalles internos como el ID del proyecto
        self.assertNotIn('123456', data['error']['message'])

    def test_catalog_client_error_returns_controlled_502(self):
        class FailingCatalog:
            def get_products_by_ids(self, ids):
                raise CatalogClientUnavailableError("Connection refused to internal host django:8000")

        broken_search = SearchService(
            product_repo=self.product_repo,
            catalog_client=FailingCatalog(),
            embedding_provider=self.embedder,
            embedding_dim=4,
        )
        self.app.config['CHAT_SERVICE'] = ChatService(
            conversation_repo=self.conv_repo,
            search_service=broken_search,
            text_generator=self.text_gen,
        )

        resp = self.client.post('/api/chatbot/message/', json={'message': 'Hola'})
        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertEqual(data['error']['code'], 'catalog_unavailable')
        self.assertNotIn('django:8000', data['error']['message'])

    def test_internal_sync_endpoint_validation_auth_and_redis_failure(self):
        enqueued_events = []
        self.app.config['SYNC_TASK_ENQUEUER'] = lambda pid, ev: enqueued_events.append((pid, ev))

        # 1. Sin header X-Internal-Key -> 401
        r_unauth = self.client.post('/internal/products/sync', json={'product_id': 11, 'event': 'upserted'})
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Payload inválido -> 400
        headers = {'X-Internal-Key': 'secret-internal-key'}
        r_bad = self.client.post(
            '/internal/products/sync',
            json={'product_id': -5, 'event': 'invalid'},
            headers=headers,
        )
        self.assertEqual(r_bad.status_code, 400)

        # 3. Petición válida -> 202 y encola tarea
        r_ok = self.client.post(
            '/internal/products/sync',
            json={'product_id': 11, 'event': 'upserted'},
            headers=headers,
        )
        self.assertEqual(r_ok.status_code, 202)
        self.assertEqual(r_ok.get_json()['status'], 'queued')
        self.assertEqual(enqueued_events, [(11, 'upserted')])

        # 4. Fallo de Redis al encolar -> 503 controlado
        def failing_enqueuer(pid, ev):
            raise ConnectionError("Redis connection refused at redis:6379")

        self.app.config['SYNC_TASK_ENQUEUER'] = failing_enqueuer
        r_redis_down = self.client.post(
            '/internal/products/sync',
            json={'product_id': 11, 'event': 'upserted'},
            headers=headers,
        )
        self.assertEqual(r_redis_down.status_code, 503)
        self.assertEqual(r_redis_down.get_json()['error']['code'], 'queue_unavailable')
        self.assertNotIn('redis:6379', r_redis_down.get_json()['error']['message'])

    def test_full_integration_flow_sync_then_chat_multi_turn(self):
        # Agregar un producto nuevo al catálogo simulado de Django
        self.catalog.add_product({
            'id': 25,
            'name': 'Chaqueta impermeable verde',
            'description': 'Ideal para lluvia y frío en ciudad.',
            'price': '129900.00',
            'stock': 8,
            'color': 'verde',
            'material': 'nylon',
            'gender': 'hombre',
            'available_sizes': ['M', 'L', 'XL'],
            'style': 'urbano',
            'category': {'id': 4, 'name': 'Chaquetas', 'description': ''},
        })
        self.embedder.mapping['Chaqueta impermeable verde'] = [0.0, 1.0, 0.0, 0.0]
        self.embedder.mapping['lluvia verde'] = [0.0, 1.0, 0.0, 0.0]

        # Sincronizar vía endpoint interno ejecutando el indexador real
        self.app.config['SYNC_TASK_ENQUEUER'] = lambda pid, ev: (
            self.indexer.upsert_product(pid) if ev == 'upserted' else self.indexer.delete_product(pid)
        )
        headers = {'X-Internal-Key': 'secret-internal-key'}
        sync_resp = self.client.post(
            '/internal/products/sync',
            json={'product_id': 25, 'event': 'upserted'},
            headers=headers,
        )
        self.assertEqual(sync_resp.status_code, 202)
        self.assertIsNotNone(self.product_repo.get(25))

        # Turno 1 de conversación: buscar la chaqueta recién indexada
        self.text_gen.queue_response(json.dumps({
            'search_text': 'lluvia verde',
            'color': 'verde',
            'size': 'L',
            'style': 'urbano',
        }))
        self.text_gen.queue_response("Para la lluvia te recomiendo la Chaqueta impermeable verde en talla L.")

        chat_resp1 = self.client.post('/api/chatbot/message/', json={
            'message': '¿Tienes alguna chaqueta urbana verde talla L para la lluvia?',
        })
        self.assertEqual(chat_resp1.status_code, 200)
        body1 = chat_resp1.get_json()
        conv_id = body1['conversation_id']
        self.assertEqual([p['id'] for p in body1['products']], [25])

        # Ahora el producto se elimina en Django y se notifica deleted
        self.catalog.remove_product(25)
        self.client.post(
            '/internal/products/sync',
            json={'product_id': 25, 'event': 'deleted'},
            headers=headers,
        )
        self.assertIsNone(self.product_repo.get(25))

        # Turno 2 en la misma conversación: ya no debe aparecer el producto 25
        self.text_gen.queue_response(json.dumps({
            'search_text': 'lluvia verde',
            'color': 'verde',
        }))
        self.text_gen.queue_response("Esa chaqueta ya no se encuentra disponible.")

        chat_resp2 = self.client.post('/api/chatbot/message/', json={
            'conversation_id': conv_id,
            'message': '¿Sigue disponible la chaqueta verde?',
        })
        self.assertEqual(chat_resp2.status_code, 200)
        body2 = chat_resp2.get_json()
        self.assertEqual(body2['conversation_id'], conv_id)
        self.assertEqual(body2['products'], [])


if __name__ == '__main__':
    unittest.main()
