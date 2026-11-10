from pathlib import Path
import tempfile
from typing import Dict, List
import unittest

from app.db.repositories import ProductRepository
from app.db.sqlite import init_db
from app.providers.base import EmbeddingProvider, FakeEmbeddingProvider
from app.services.catalog_client import FakeCatalogClient
from app.services.indexer import (
    IndexerService,
    InvalidEmbeddingError,
    build_embedding_text,
    compute_product_hash,
)
from app.services.search import SearchService, sanitize_filters
from app.tasks.indexing import reindex_catalog_task, sync_product_task


class ControlledEmbeddingProvider(EmbeddingProvider):
    """Proveedor de embeddings con vectores predefinidos por subcadena para probar ranking y coseno."""

    def __init__(self, mapping: Dict[str, List[float]], default_vec: List[float]):
        self.mapping = mapping
        self.default_vec = default_vec
        self.doc_calls: List[str] = []
        self.query_calls: List[str] = []

    def _resolve(self, text: str) -> List[float]:
        for key, vec in self.mapping.items():
            if key.lower() in text.lower():
                return list(vec)
        return list(self.default_vec)

    def embed_document(self, text: str) -> List[float]:
        self.doc_calls.append(text)
        return self._resolve(text)

    def embed_query(self, text: str) -> List[float]:
        self.query_calls.append(text)
        return self._resolve(text)


def _make_sample_products() -> List[dict]:
    return [
        {
            'id': 1,
            'name': 'Camiseta básica blanca',
            'description': 'Algodón fresco para uso diario.',
            'price': '39900.00',
            'stock': 15,
            'color': 'blanco',
            'material': 'algodón',
            'gender': 'unisex',
            'available_sizes': ['S', 'M', 'L'],
            'style': 'casual',
            'category': {'id': 1, 'name': 'Camisetas', 'description': ''},
        },
        {
            'id': 2,
            'name': 'Short deportivo azul',
            'description': 'Secado rápido para entrenamiento.',
            'price': '49900.00',
            'stock': 20,
            'color': 'azul',
            'material': 'poliéster',
            'gender': 'hombre',
            'available_sizes': ['M', 'L', 'XL'],
            'style': 'deportivo',
            'category': {'id': 2, 'name': 'Ropa deportiva', 'description': ''},
        },
        {
            'id': 3,
            'name': 'Vestido floral elegante',
            'description': 'Corte largo para eventos de noche.',
            'price': '149900.00',
            'stock': 5,
            'color': 'rojo',
            'material': 'seda',
            'gender': 'mujer',
            'available_sizes': ['XS', 'S', 'M'],
            'style': 'elegante',
            'category': {'id': 3, 'name': 'Vestidos', 'description': ''},
        },
        {
            'id': 4,
            'name': 'Chaqueta denim urbana',
            'description': 'Chaqueta resistente estilo streetwear.',
            'price': '189900.00',
            'stock': 0,  # Agotada
            'color': 'azul',
            'material': 'denim',
            'gender': 'unisex',
            'available_sizes': ['M', 'L'],
            'style': 'urbano',
            'category': {'id': 4, 'name': 'Chaquetas', 'description': ''},
        },
    ]


class IndexingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_index.sqlite3')
        init_db(self.db_path)
        self.repo = ProductRepository(self.db_path)
        self.catalog = FakeCatalogClient(_make_sample_products())
        self.embedder = FakeEmbeddingProvider(dim=8)
        self.indexer = IndexerService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=self.embedder,
            embedding_model='gemini-embedding-001',
            embedding_dim=8,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_embedding_text_and_hash_ignore_price_and_stock(self):
        p1 = _make_sample_products()[0]
        p2 = dict(p1, price='999999.00', stock=0, available_sizes=['L', 'S', 'M'])

        self.assertEqual(build_embedding_text(p1), build_embedding_text(p2))
        self.assertEqual(compute_product_hash(p1), compute_product_hash(p2))

        # Cambiar un atributo semántico sí modifica el hash
        p3 = dict(p1, color='negro')
        self.assertNotEqual(compute_product_hash(p1), compute_product_hash(p3))

    def test_upsert_product_skips_reembedding_when_only_price_or_stock_changes(self):
        status1 = self.indexer.upsert_product(1)
        self.assertEqual(status1, 'indexed')
        self.assertEqual(len(self.embedder.embedded_documents), 1)

        # Modificar precio y stock en el catálogo
        prod = self.catalog.get_product(1)
        prod['price'] = '55000.00'
        prod['stock'] = 2
        self.catalog.add_product(prod)

        status2 = self.indexer.upsert_product(1)
        self.assertEqual(status2, 'unchanged')
        # No se volvió a llamar al proveedor de embeddings
        self.assertEqual(len(self.embedder.embedded_documents), 1)

    def test_upsert_product_reembeds_when_semantic_field_changes(self):
        self.indexer.upsert_product(1)
        old_hash = self.repo.get_hash(1)

        prod = self.catalog.get_product(1)
        prod['description'] = 'Algodón orgánico premium renovado.'
        self.catalog.add_product(prod)

        status = self.indexer.upsert_product(1)
        self.assertEqual(status, 'indexed')
        self.assertEqual(len(self.embedder.embedded_documents), 2)
        self.assertNotEqual(self.repo.get_hash(1), old_hash)

    def test_upsert_product_deletes_from_index_if_404_in_django(self):
        self.indexer.upsert_product(1)
        self.assertIsNotNone(self.repo.get(1))

        self.catalog.remove_product(1)
        status = self.indexer.upsert_product(1)
        self.assertEqual(status, 'deleted_missing')
        self.assertIsNone(self.repo.get(1))

    def test_invalid_embedding_raises_error_and_does_not_save(self):
        class BrokenEmbedder(EmbeddingProvider):
            def embed_document(self, text: str) -> List[float]:
                return [0.1, 0.2]  # Dimensión 2 en lugar de 8

            def embed_query(self, text: str) -> List[float]:
                return [0.1, 0.2]

        bad_indexer = IndexerService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=BrokenEmbedder(),
            embedding_dim=8,
        )
        with self.assertRaises(InvalidEmbeddingError):
            bad_indexer.upsert_product(1)
        self.assertIsNone(self.repo.get(1))

    def test_reindex_catalog_paginates_and_removes_stale_products(self):
        # Insertar un producto obsoleto (id 999) que no existe en Django
        self.repo.upsert(999, 'stale_hash', [0.5] * 8, 'gemini-embedding-001', 8)

        summary1 = self.indexer.reindex_catalog(page_size=2)
        self.assertEqual(summary1['indexed'], 4)
        self.assertEqual(summary1['unchanged'], 0)
        self.assertEqual(summary1['deleted'], 1)
        self.assertEqual(summary1['total_seen'], 4)
        self.assertIsNone(self.repo.get(999))

        # Segunda ejecución sin cambios no re-embebe nada
        summary2 = self.indexer.reindex_catalog(page_size=2)
        self.assertEqual(summary2['indexed'], 0)
        self.assertEqual(summary2['unchanged'], 4)
        self.assertEqual(summary2['deleted'], 0)

    def test_celery_task_wrappers(self):
        res_up = sync_product_task(1, event='upserted', indexer=self.indexer)
        self.assertEqual(res_up['status'], 'indexed')

        res_del = sync_product_task(1, event='deleted', indexer=self.indexer)
        self.assertEqual(res_del['status'], 'deleted')

        res_reindex = reindex_catalog_task(page_size=2, indexer=self.indexer)
        self.assertEqual(res_reindex['indexed'], 4)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_search.sqlite3')
        init_db(self.db_path)
        self.repo = ProductRepository(self.db_path)
        self.catalog = FakeCatalogClient(_make_sample_products())

        # Vectores controlados en 4D para pruebas exactas de similitud por coseno
        self.mapping = {
            'Camiseta básica blanca': [1.0, 0.0, 0.0, 0.0],
            'Short deportivo azul': [0.8, 0.6, 0.0, 0.0],
            'Vestido floral elegante': [0.0, 0.0, 1.0, 0.0],
            'Chaqueta denim urbana': [0.0, 0.0, 0.0, 1.0],
            # Consultas de prueba
            'consulta_deporte_fresco': [1.0, 0.0, 0.0, 0.0],  # coseno: id1=1.0, id2=0.8, id3=0.0, id4=0.0
            'consulta_chaqueta_agotada': [0.0, 0.0, 0.0, 1.0],  # coseno: id4=1.0 (stock=0)
            'consulta_irrelevante': [-1.0, 0.0, 0.0, 0.0],  # cosenos <= 0
        }
        self.embedder = ControlledEmbeddingProvider(
            mapping=self.mapping,
            default_vec=[0.5, 0.5, 0.5, 0.5],
        )
        self.indexer = IndexerService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=self.embedder,
            embedding_dim=4,
        )
        self.indexer.reindex_catalog()

        self.search_service = SearchService(
            product_repo=self.repo,
            catalog_client=self.catalog,
            embedding_provider=self.embedder,
            similarity_threshold=0.55,
            top_k=10,
            max_results=4,
            embedding_dim=4,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cosine_ranking_and_threshold(self):
        result = self.search_service.search('consulta_deporte_fresco')
        self.assertEqual(result['status'], 'ok')
        # Solo id 1 (score 1.0) e id 2 (score 0.8) superan el umbral 0.55 y tienen stock > 0
        ids = [p['id'] for p in result['products']]
        self.assertEqual(ids, [1, 2])
        self.assertAlmostEqual(result['products'][0]['similarity_score'], 1.0, places=3)
        self.assertAlmostEqual(result['products'][1]['similarity_score'], 0.8, places=3)

    def test_threshold_filters_out_irrelevant_queries(self):
        result = self.search_service.search('consulta_irrelevante')
        self.assertEqual(result['status'], 'no_results')
        self.assertEqual(result['products'], [])

    def test_out_of_stock_product_is_not_recommended_as_available(self):
        result = self.search_service.search('consulta_chaqueta_agotada')
        self.assertEqual(result['status'], 'only_out_of_stock')
        self.assertEqual(result['products'], [])
        self.assertEqual(len(result['out_of_stock']), 1)
        self.assertEqual(result['out_of_stock'][0]['id'], 4)

    def test_deleted_product_in_django_is_discarded_even_if_still_in_index(self):
        # Eliminar producto 1 de Django sin borrarlo del índice SQLite
        self.catalog.remove_product(1)
        result = self.search_service.search('consulta_deporte_fresco')
        ids = [p['id'] for p in result['products']]
        self.assertEqual(ids, [2])

    def test_strict_filters_price_color_size_gender_style(self):
        # Filtro por precio máximo (usa precio fresco de Django)
        res_price = self.search_service.search(
            'consulta_deporte_fresco',
            filters={'max_price': '45000'},
        )
        self.assertEqual([p['id'] for p in res_price['products']], [1])

        # Filtro por color azul -> solo id 2 (entre los que superan el umbral y tienen stock)
        res_color = self.search_service.search(
            'consulta_deporte_fresco',
            filters={'color': 'AZUL'},
        )
        self.assertEqual([p['id'] for p in res_color['products']], [2])

        # Filtro por talla XL -> solo id 2 tiene XL en available_sizes
        res_size = self.search_service.search(
            'consulta_deporte_fresco',
            filters={'size': 'xl'},
        )
        self.assertEqual([p['id'] for p in res_size['products']], [2])

        # Filtro por género mujer -> acepta 'mujer' y 'unisex' (id 1 es unisex, id 2 es hombre)
        res_gender = self.search_service.search(
            'consulta_deporte_fresco',
            filters={'gender': 'mujer'},
        )
        self.assertEqual([p['id'] for p in res_gender['products']], [1])

        # Filtro por estilo deportivo -> solo id 2
        res_style = self.search_service.search(
            'consulta_deporte_fresco',
            filters={'style': 'deportivo'},
        )
        self.assertEqual([p['id'] for p in res_style['products']], [2])

    def test_sanitize_filters_discards_invalid_enum_values(self):
        cleaned = sanitize_filters({
            'size': 'XXL',  # Inválido
            'gender': 'infantil',  # Inválido
            'style': 'gotico',  # Inválido
            'max_price': 'no-numero',  # Inválido
            'color': ' Verde ',
        })
        self.assertNotIn('size', cleaned)
        self.assertNotIn('gender', cleaned)
        self.assertNotIn('style', cleaned)
        self.assertNotIn('max_price', cleaned)
        self.assertEqual(cleaned.get('color'), 'verde')


if __name__ == '__main__':
    unittest.main()
