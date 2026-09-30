import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from .infra.factory import NotificationFactory
from .infra.notifications import RemoteNotification
from .models import Cart, CartItem, Category, Order, Product
from .services import OrderService


@override_settings(NOTIFICATIONS_BACKEND='remote', NOTIFICATIONS_API_KEY='test-key',
                   NOTIFICATIONS_URL='http://localhost:5000/api/v2/notifications/',
                   NOTIFICATIONS_TIMEOUT=2)
class RemoteNotificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ana')
        category = Category.objects.create(name='Ropa')
        self.product = Product.objects.create(name='Camisa', price=10, stock=4, category=category)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

    def test_factory(self):
        self.assertIsInstance(NotificationFactory.create(), RemoteNotification)

    @patch('urllib.request.urlopen')
    def test_json_contract(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = b'{"status":"simulated"}'
        order = SimpleNamespace(id=9, user=self.user)
        self.assertEqual(RemoteNotification().send_confirmation(order)['status'], 'simulated')
        request = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request.data)['order_id'], 9)
        self.assertEqual(urlopen.call_args.kwargs['timeout'], 2)

    @patch('urllib.request.urlopen', side_effect=URLError('offline'))
    def test_failure_keeps_confirmed_order(self, urlopen):
        with self.assertLogs('Volt.infra.notifications', level='ERROR'):
            with self.captureOnCommitCallbacks(execute=True):
                order = OrderService().create_order(self.user)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertFalse(CartItem.objects.filter(cart__user=self.user).exists())

    @patch('Volt.infra.notifications.RemoteNotification.send_confirmation')
    def test_only_after_commit(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            OrderService().create_order(self.user)
            send.assert_not_called()
        send.assert_called_once()

    @patch('Volt.infra.notifications.RemoteNotification.send_confirmation')
    def test_rollback_does_not_notify(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    OrderService().create_order(self.user)
                    raise ValueError('rollback')
            except ValueError:
                pass
        send.assert_not_called()
        self.assertEqual(Order.objects.count(), 0)

    def test_versioned_legacy_route(self):
        self.assertEqual(self.client.get('/api/v1/categories/').status_code, 200)
        self.assertEqual(self.client.get('/api/categories/').status_code, 200)
