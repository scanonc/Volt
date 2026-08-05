from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Cart, CartItem, Category, Order, Product
from .services import OrderService


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='12345')
        self.category = Category.objects.create(name='Ropa', description='Prendas básicas')
        self.product = Product.objects.create(
            name='Camisa',
            description='Camisa de algodón',
            price=Decimal('15000.00'),
            stock=10,
            category=self.category,
        )
        self.cart = Cart.objects.create(user=self.user)

    def test_create_order_from_cart(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)

        order = OrderService().create_order(self.user)

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total, Decimal('30000.00'))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)

    def test_create_order_requires_products(self):
        with self.assertRaises(ValueError):
            OrderService().create_order(self.user)

    def test_get_orders_endpoint_returns_instructions(self):
        response = self.client.get('/api/orders/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Use POST', response.json()['message'])
