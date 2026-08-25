from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .domain.builders import OrderBuilder
from .models import Address, Cart, CartItem, Category, Order, Product
from .services import (
    AddressNotFoundError,
    CartNotFoundError,
    EmptyCartError,
    InsufficientStockError,
    InvalidAddressError,
    OrderService,
)


class OrderBuilderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='builder-user', password='12345')
        self.other_user = get_user_model().objects.create_user(username='other-user', password='12345')
        self.category = Category.objects.create(name='Builder Category')
        self.product = Product.objects.create(
            name='Builder Product',
            price=Decimal('50.00'),
            stock=10,
            category=self.category,
        )
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.address = Address.objects.create(
            user=self.user,
            street='Calle 10 # 20-30',
            city='Bogota',
            state='Cundinamarca',
            zip_code='110111',
        )
        self.other_address = Address.objects.create(
            user=self.other_user,
            street='Carrera 7 # 45-67',
            city='Medellin',
            state='Antioquia',
            zip_code='050001',
        )

    def test_build_with_valid_shipping_address(self):
        order, items = (
            OrderBuilder()
            .for_user(self.user)
            .with_items([self.cart_item])
            .with_shipping_address(self.address)
            .build()
        )
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.shipping_address, self.address)
        self.assertEqual(len(items), 1)

    def test_build_rejects_shipping_address_of_another_user(self):
        with self.assertRaises(ValueError):
            (
                OrderBuilder()
                .for_user(self.user)
                .with_items([self.cart_item])
                .with_shipping_address(self.other_address)
                .build()
            )


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

    def test_create_order_with_explicit_shipping_address(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        address = Address.objects.create(
            user=self.user,
            street='Calle 100 # 15-20',
            city='Bogota',
            state='Cundinamarca',
            zip_code='110221',
        )

        order = OrderService().create_order(self.user, shipping_address_id=address.id)

        self.assertEqual(order.shipping_address, address)

    def test_create_order_with_default_shipping_address(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        default_address = Address.objects.create(
            user=self.user,
            street='Avenida 19 # 100-50',
            city='Bogota',
            state='Cundinamarca',
            zip_code='110111',
            is_default=True,
        )

        order = OrderService().create_order(self.user)

        self.assertEqual(order.shipping_address, default_address)

    def test_create_order_rejects_address_of_another_user(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        other_user = get_user_model().objects.create_user(username='other-svc-user', password='12345')
        other_address = Address.objects.create(
            user=other_user,
            street='Calle 50 # 10-20',
            city='Cali',
            state='Valle',
            zip_code='760001',
        )

        with self.assertRaises(InvalidAddressError):
            OrderService().create_order(self.user, shipping_address_id=other_address.id)

    def test_create_order_rejects_non_existent_address(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

        with self.assertRaises(AddressNotFoundError):
            OrderService().create_order(self.user, shipping_address_id=99999)

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

    def test_post_orders_with_explicit_shipping_address(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        address = Address.objects.create(
            user=self.user,
            street='Carrera 15 # 85-30',
            city='Bogota',
            state='Cundinamarca',
            zip_code='110221',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            data={'shipping_address_id': address.id},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        order_data = response.json()['order']
        self.assertIsNotNone(order_data['shipping_address'])
        self.assertEqual(order_data['shipping_address']['id'], address.id)
        self.assertEqual(order_data['shipping_address']['street'], 'Carrera 15 # 85-30')

    def test_post_orders_with_default_shipping_address(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        default_address = Address.objects.create(
            user=self.user,
            street='Transversal 23 # 95-10',
            city='Bogota',
            state='Cundinamarca',
            zip_code='110111',
            is_default=True,
        )
        self.client.force_login(self.user)

        response = self.client.post(self.url, data={}, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        order_data = response.json()['order']
        self.assertIsNotNone(order_data['shipping_address'])
        self.assertEqual(order_data['shipping_address']['id'], default_address.id)

    def test_post_orders_rejects_address_of_another_user(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        other_user = get_user_model().objects.create_user(username='other-api-user', password='12345')
        other_address = Address.objects.create(
            user=other_user,
            street='Calle 1 # 2-3',
            city='Barranquilla',
            state='Atlantico',
            zip_code='080001',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            data={'shipping_address_id': other_address.id},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_post_orders_rejects_non_existent_address(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            data={'shipping_address_id': 99999},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)

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


class AddressApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='addr-user', password='12345')
        self.other_user = get_user_model().objects.create_user(username='other-addr-user', password='12345')
        self.address = Address.objects.create(
            user=self.user,
            street='Calle 123 # 45-67',
            city='Bogota',
            state='Cundinamarca',
            zip_code='110111',
            country='Colombia',
            is_default=True,
        )
        self.other_address = Address.objects.create(
            user=self.other_user,
            street='Carrera 80 # 30-10',
            city='Medellin',
            state='Antioquia',
            zip_code='050001',
            country='Colombia',
            is_default=False,
        )
        self.list_url = '/api/addresses/'

    def test_list_addresses_requires_auth(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 401)

    def test_list_addresses_returns_only_user_addresses(self):
        self.client.force_login(self.user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.address.id)
        self.assertEqual(data[0]['street'], 'Calle 123 # 45-67')

    def test_create_address_requires_auth(self):
        payload = {
            'street': 'Nueva Calle 1 # 2-3',
            'city': 'Cali',
            'state': 'Valle',
            'zip_code': '760001',
            'country': 'Colombia',
            'is_default': False,
        }
        response = self.client.post(self.list_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_create_address_success(self):
        self.client.force_login(self.user)
        payload = {
            'street': 'Nueva Calle 1 # 2-3',
            'city': 'Cali',
            'state': 'Valle',
            'zip_code': '760001',
            'country': 'Colombia',
            'is_default': False,
        }
        response = self.client.post(self.list_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        created_address = Address.objects.get(id=response.json()['id'])
        self.assertEqual(created_address.user, self.user)
        self.assertEqual(created_address.street, 'Nueva Calle 1 # 2-3')
        self.assertEqual(created_address.city, 'Cali')

    def test_create_address_invalid_data(self):
        self.client.force_login(self.user)
        payload = {
            'city': 'Cali',
        }
        response = self.client.post(self.list_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('street', response.json()['errors'])

    def test_address_detail_requires_auth(self):
        response = self.client.get(f'{self.list_url}{self.address.id}/')
        self.assertEqual(response.status_code, 401)

    def test_address_detail_success_for_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(f'{self.list_url}{self.address.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.address.id)
        self.assertEqual(response.json()['street'], 'Calle 123 # 45-67')

    def test_address_detail_returns_404_for_other_user_address(self):
        self.client.force_login(self.user)
        response = self.client.get(f'{self.list_url}{self.other_address.id}/')

        self.assertEqual(response.status_code, 404)

    def test_address_detail_returns_404_when_missing(self):
        self.client.force_login(self.user)
        response = self.client.get(f'{self.list_url}99999/')

        self.assertEqual(response.status_code, 404)


class ProductDomainTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Accesorios')
        self.product = Product.objects.create(
            name='Gorra',
            description='Gorra de algodón',
            price=Decimal('25000.00'),
            stock=5,
            category=self.category,
        )

    def test_has_stock(self):
        self.assertTrue(self.product.has_stock(5))
        self.assertFalse(self.product.has_stock(6))

    def test_reduce_stock_discounts_quantity(self):
        self.product.reduce_stock(3)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

    def test_reduce_stock_rejects_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            self.product.reduce_stock(6)

    def test_reduce_stock_rejects_non_positive_quantity(self):
        with self.assertRaises(ValidationError):
            self.product.reduce_stock(0)


class CatalogApiTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Calzado')
        self.product = Product.objects.create(
            name='Tenis',
            description='Tenis urbanos',
            price=Decimal('120000.00'),
            stock=8,
            category=self.category,
        )

    def test_list_categories(self):
        response = self.client.get('/api/categories/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['name'], 'Calzado')

    def test_list_products(self):
        response = self.client.get('/api/products/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['name'], 'Tenis')

    def test_list_products_filtered_by_category(self):
        other_category = Category.objects.create(name='Ropa Deportiva')
        response = self.client.get(f'/api/products/?category={other_category.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_product_detail_returns_200(self):
        response = self.client.get(f'/api/products/{self.product.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Tenis')

    def test_product_detail_returns_404_when_missing(self):
        response = self.client.get('/api/products/9999/')

        self.assertEqual(response.status_code, 404)
