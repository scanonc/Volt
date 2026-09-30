import unittest
from unittest.mock import patch
from app import create_app


class NotificationAPITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'NOTIFICATIONS_API_KEY': 'test-key'})
        self.client = self.app.test_client()
        self.headers = {'X-API-Key': 'test-key'}

    def post(self, data):
        return self.client.post('/api/v2/notifications/', json=data, headers=self.headers)

    def test_channels(self):
        for channel in ('console', 'email'):
            with self.subTest(channel=channel):
                response = self.post({'order_id': 7, 'username': 'ana', 'channel': channel})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['status'], 'simulated')
                self.assertEqual(response.json['channel'], channel)

    def test_invalid_payloads(self):
        for data in ([], {}, {'order_id': True, 'username': 'ana'},
                     {'order_id': -1, 'username': 'ana'}, {'order_id': 1, 'username': ''},
                     {'order_id': 1, 'username': 'ana', 'channel': 'sms'}):
            with self.subTest(data=data):
                response = self.post(data)
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json)

    def test_malformed_json(self):
        response = self.client.post('/api/v2/notifications/', data='{',
                                    content_type='application/json', headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_authentication(self):
        self.assertEqual(self.client.post('/api/v2/notifications/', json={}).status_code, 401)

    def test_unconfigured(self):
        self.app.config['NOTIFICATIONS_API_KEY'] = ''
        self.assertEqual(self.post({}).status_code, 503)

    def test_structured_internal_error(self):
        with patch.object(self.app.logger, 'info', side_effect=RuntimeError('private detail')):
            with self.assertLogs(self.app.logger, level='ERROR'):
                response = self.post({'order_id': 1, 'username': 'ana'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json['error']['code'], 'internal_error')
        self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_health_and_not_found(self):
        self.assertEqual(self.client.get('/health/').status_code, 200)
        self.assertEqual(self.client.get('/unknown').status_code, 404)
        self.assertIn('error', self.client.get('/unknown').json)
