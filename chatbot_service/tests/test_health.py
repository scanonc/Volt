import unittest
from app import create_app


class HealthAndErrorHandlerTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'CHATBOT_DB_PATH': ':memory:',
            'INIT_DB_ON_STARTUP': False,
        })
        self.client = self.app.test_client()

    def test_health_returns_ok_and_service_name(self):
        response = self.client.get('/api/chatbot/health/')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('service'), 'chatbot')

    def test_404_returns_clean_json_error(self):
        response = self.client.get('/api/chatbot/non-existent-endpoint/')
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], 'http_error')

    def test_500_handler_returns_clean_json_without_internal_leak(self):
        # Registrar una ruta de prueba que falle intencionalmente
        @self.app.route('/test-crash/')
        def crash():
            raise RuntimeError("Secret internal database connection string failed!")

        response = self.client.get('/test-crash/')
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], 'internal_error')
        # Asegurarse de que no filtra el mensaje de la excepción interna
        self.assertNotIn("Secret internal database", data['error']['message'])


if __name__ == '__main__':
    unittest.main()
