from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Cart, CartItem, Category, Order, Product
from .services import CartNotFoundError, EmptyCartError, InsufficientStockError, OrderService


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
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_create_order_requires_products(self):
        with self.assertRaises(EmptyCartError):
            OrderService().create_order(self.user)

    def test_create_order_requires_existing_cart(self):
        another_user = get_user_model().objects.create_user(username='no-cart', password='12345')

        with self.assertRaises(CartNotFoundError):
            OrderService().create_order(another_user)

    def test_create_order_fails_when_stock_is_insufficient(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=20)

        with self.assertRaises(InsufficientStockError):
            OrderService().create_order(self.user)


class CreateOrderApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='api-user', password='12345')
        self.category = Category.objects.create(name='Ropa API', description='Prendas API')
        self.product = Product.objects.create(
            name='Pantalon',
            description='Pantalon de prueba',
            price=Decimal('20000.00'),
            stock=5,
            category=self.category,
        )
        self.url = '/api/orders/'

    def test_get_orders_endpoint_returns_instructions(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Use POST', response.json()['message'])

    def test_post_orders_requires_authentication(self):
        response = self.client.post(self.url, data={}, content_type='application/json')

        self.assertEqual(response.status_code, 401)

    def test_post_orders_creates_order_and_returns_201(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.client.force_login(self.user)

        response = self.client.post(self.url, data={}, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['order']['status'], Order.Status.PENDING)
        self.assertEqual(response.json()['order']['total'], '40000.00')

    def test_post_orders_returns_404_when_user_has_no_cart(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, data={}, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_post_orders_returns_400_when_cart_is_empty(self):
        Cart.objects.create(user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(self.url, data={}, content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_post_orders_returns_409_when_stock_is_insufficient(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=10)
        self.client.force_login(self.user)

        response = self.client.post(self.url, data={}, content_type='application/json')

        self.assertEqual(response.status_code, 409)
