from unittest.mock import MagicMock, patch
import unittest
import requests

from app.services.catalog_client import (
    CatalogClient,
    CatalogClientError,
    CatalogClientNotFoundError,
    CatalogClientTimeoutError,
    CatalogClientUnavailableError,
    FakeCatalogClient,
)


class FakeCatalogClientTests(unittest.TestCase):
    def setUp(self):
        self.sample_products = [
            {'id': 1, 'name': 'Camiseta', 'price': '39900.00', 'stock': 10},
            {'id': 2, 'name': 'Pantalón', 'price': '89900.00', 'stock': 5},
            {'id': 3, 'name': 'Chaqueta', 'price': '150000.00', 'stock': 2},
        ]
        self.client = FakeCatalogClient(self.sample_products)

    def test_get_product(self):
        p1 = self.client.get_product(1)
        self.assertIsNotNone(p1)
        self.assertEqual(p1['name'], 'Camiseta')
        self.assertIsNone(self.client.get_product(99))

    def test_add_and_remove_product(self):
        self.client.add_product({'id': 4, 'name': 'Gorra', 'price': '25000.00', 'stock': 8})
        self.assertIsNotNone(self.client.get_product(4))

        self.client.remove_product(4)
        self.assertIsNone(self.client.get_product(4))

    def test_get_products_by_ids(self):
        items = self.client.get_products_by_ids([1, 3, 999])
        self.assertEqual(len(items), 2)
        names = {item['name'] for item in items}
        self.assertEqual(names, {'Camiseta', 'Chaqueta'})

    def test_list_products_pagination(self):
        p_page1 = self.client.list_products(limit=2, offset=0)
        self.assertEqual(len(p_page1), 2)
        self.assertEqual(p_page1[0]['id'], 1)
        self.assertEqual(p_page1[1]['id'], 2)

        p_page2 = self.client.list_products(limit=2, offset=2)
        self.assertEqual(len(p_page2), 1)
        self.assertEqual(p_page2[0]['id'], 3)


class CatalogClientHTTPTests(unittest.TestCase):
    def setUp(self):
        self.client = CatalogClient(base_url='http://django:8000', timeout=2.0)

    @patch('app.services.catalog_client.requests.get')
    def test_get_product_200(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'id': 10, 'name': 'Zapato'}
        mock_get.return_value = mock_resp

        data = self.client.get_product(10)
        self.assertEqual(data['id'], 10)
        mock_get.assert_called_once_with('http://django:8000/api/v1/products/10/', timeout=2.0)

    @patch('app.services.catalog_client.requests.get')
    def test_get_product_404(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        data = self.client.get_product(999)
        self.assertIsNone(data)

    @patch('app.services.catalog_client.requests.get')
    def test_get_product_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timed out")
        with self.assertRaises(CatalogClientTimeoutError):
            self.client.get_product(5)

    @patch('app.services.catalog_client.requests.get')
    def test_get_product_500_unavailable(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        with self.assertRaises(CatalogClientUnavailableError):
            self.client.get_product(5)

    @patch('app.services.catalog_client.requests.get')
    def test_get_products_by_ids(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{'id': 1}, {'id': 2}]
        mock_get.return_value = mock_resp

        data = self.client.get_products_by_ids([1, 2])
        self.assertEqual(len(data), 2)
        mock_get.assert_called_once_with('http://django:8000/api/v1/products/?ids=1,2', timeout=2.0)

    def test_get_products_by_ids_empty(self):
        data = self.client.get_products_by_ids([])
        self.assertEqual(data, [])

    @patch('app.services.catalog_client.requests.get')
    def test_list_products_pagination(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{'id': 50}]
        mock_get.return_value = mock_resp

        data = self.client.list_products(limit=50, offset=100)
        self.assertEqual(len(data), 1)
        mock_get.assert_called_once_with('http://django:8000/api/v1/products/?limit=50&offset=100', timeout=2.0)


if __name__ == '__main__':
    unittest.main()
