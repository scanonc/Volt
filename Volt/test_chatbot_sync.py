from decimal import Decimal
import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from Volt.models import Category, Product


@override_settings(
    CHATBOT_SYNC_URL='http://chatbot:5001/internal/products/sync',
    CHATBOT_INTERNAL_API_KEY='test-internal-key',
    CHATBOT_SYNC_TIMEOUT=2.0,
)
class ChatbotSyncSignalsTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Ropa Deportiva')

    @patch('Volt.signals.urlopen')
    def test_product_create_sends_upserted_event(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.captureOnCommitCallbacks(execute=True):
            product = Product.objects.create(
                name='Pantalón deportivo',
                price=Decimal('79900.00'),
                stock=10,
                category=self.category,
                color='negro',
                material='poliéster',
                gender='unisex',
                available_sizes=['M', 'L'],
                style='deportivo',
            )

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, 'http://chatbot:5001/internal/products/sync')
        self.assertEqual(req.headers.get('X-internal-key'), 'test-internal-key')

        body = json.loads(req.data.decode('utf-8'))
        self.assertEqual(body['product_id'], product.id)
        self.assertEqual(body['event'], 'upserted')

    @patch('Volt.signals.urlopen')
    def test_product_update_sends_upserted_event(self, mock_urlopen):
        product = Product.objects.create(
            name='Camiseta blanca',
            price=Decimal('35000.00'),
            stock=5,
            category=self.category,
        )

        mock_resp = MagicMock()
        mock_resp.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.captureOnCommitCallbacks(execute=True):
            product.description = 'Nueva descripción de algodón'
            product.save(update_fields=['description'])

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode('utf-8'))
        self.assertEqual(body['product_id'], product.id)
        self.assertEqual(body['event'], 'upserted')

    @patch('Volt.signals.urlopen')
    def test_product_stock_or_price_only_update_is_ignored(self, mock_urlopen):
        product = Product.objects.create(
            name='Buzo azul',
            price=Decimal('90000.00'),
            stock=10,
            category=self.category,
        )
        mock_urlopen.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            product.stock = 8
            product.save(update_fields=['stock'])

        # No debe haberse llamado a urlopen
        mock_urlopen.assert_not_called()

        with self.captureOnCommitCallbacks(execute=True):
            product.reduce_stock(2)

        mock_urlopen.assert_not_called()

    @patch('Volt.signals.urlopen')
    def test_product_delete_sends_deleted_event(self, mock_urlopen):
        product = Product.objects.create(
            name='Prenda a borrar',
            price=Decimal('20000.00'),
            stock=1,
            category=self.category,
        )
        pid = product.id
        mock_urlopen.reset_mock()

        mock_resp = MagicMock()
        mock_resp.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.captureOnCommitCallbacks(execute=True):
            product.delete()

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode('utf-8'))
        self.assertEqual(body['product_id'], pid)
        self.assertEqual(body['event'], 'deleted')

    @patch('Volt.signals.urlopen')
    def test_flask_failure_does_not_break_django_save_or_delete(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("Connection refused to chatbot:5001")

        # La creación debe completarse sin lanzar excepción
        with self.captureOnCommitCallbacks(execute=True):
            product = Product.objects.create(
                name='Chaqueta invernal',
                price=Decimal('150000.00'),
                stock=4,
                category=self.category,
            )
        self.assertIsNotNone(product.id)

        # El borrado debe completarse sin lanzar excepción
        with self.captureOnCommitCallbacks(execute=True):
            product.delete()
        self.assertFalse(Product.objects.filter(id=product.id).exists())


class ProductCatalogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name='Calzado')
        self.p1 = Product.objects.create(
            name='Zapato Casual',
            price=Decimal('120000.00'),
            stock=10,
            category=self.category,
            color='cafe',
            material='cuero',
            gender='hombre',
            available_sizes=['M', 'L'],
            style='casual',
        )
        self.p2 = Product.objects.create(
            name='Tenis Deportivo',
            price=Decimal('160000.00'),
            stock=5,
            category=self.category,
            color='blanco',
            material='malla',
            gender='unisex',
            available_sizes=['S', 'M', 'L', 'XL'],
            style='deportivo',
        )
        self.p3 = Product.objects.create(
            name='Bota Montaña',
            price=Decimal('220000.00'),
            stock=2,
            category=self.category,
            color='negro',
            material='cuero sintetico',
            gender='unisex',
            available_sizes=['M', 'L'],
            style='urbano',
        )

    def test_get_product_detail_includes_new_fields(self):
        resp = self.client.get(f'/api/v1/products/{self.p1.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['id'], self.p1.id)
        self.assertEqual(data['color'], 'cafe')
        self.assertEqual(data['material'], 'cuero')
        self.assertEqual(data['gender'], 'hombre')
        self.assertEqual(data['available_sizes'], ['M', 'L'])
        self.assertEqual(data['style'], 'casual')
        self.assertEqual(data['category']['name'], 'Calzado')

    def test_get_products_filter_by_ids(self):
        resp = self.client.get(f'/api/v1/products/?ids={self.p1.id},{self.p3.id}')
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertEqual(len(items), 2)
        returned_ids = [item['id'] for item in items]
        self.assertEqual(returned_ids, [self.p1.id, self.p3.id])

    def test_get_products_pagination_limit_and_offset(self):
        resp = self.client.get('/api/v1/products/?limit=2&offset=1')
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['id'], self.p2.id)
        self.assertEqual(items[1]['id'], self.p3.id)
