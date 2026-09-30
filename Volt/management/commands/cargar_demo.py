"""Datos de demostración y compra opcional usando el flujo real de pedidos."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Volt.models import Address, Cart, CartItem, Category, Product
from Volt.services import OrderService, OrderServiceError


PRODUCTS = [
    ('Camisetas', 'Camiseta básica blanca [DEMO]', 'Algodón, talla M.', '39900', 30),
    ('Camisetas', 'Camiseta oversize negra [DEMO]', 'Algodón, talla L.', '59900', 25),
    ('Camisas', 'Camisa de lino beige [DEMO]', 'Manga larga, talla M.', '119900', 15),
    ('Camisas', 'Camisa de cuadros [DEMO]', 'Franela, talla L.', '89900', 18),
    ('Pantalones', 'Jean azul clásico [DEMO]', 'Corte recto, talla 32.', '129900', 20),
    ('Pantalones', 'Pantalón cargo verde [DEMO]', 'Bolsillos laterales, talla 30.', '139900', 12),
    ('Vestidos', 'Vestido floral [DEMO]', 'Tela ligera, talla M.', '149900', 10),
    ('Chaquetas', 'Chaqueta denim [DEMO]', 'Denim azul, talla L.', '189900', 8),
    ('Buzos', 'Buzo con capota gris [DEMO]', 'Algodón perchado, talla M.', '109900', 16),
    ('Ropa deportiva', 'Leggings negros [DEMO]', 'Tela elástica, talla M.', '79900', 22),
    ('Ropa deportiva', 'Short deportivo azul [DEMO]', 'Secado rápido, talla L.', '49900', 20),
    ('Accesorios', 'Gorra beige [DEMO]', 'Talla ajustable.', '34900', 25),
]


class Command(BaseCommand):
    help = 'Carga 12 prendas, un comprador demo, dirección y carrito; --crear-pedido prueba notificaciones.'

    def add_arguments(self, parser):
        parser.add_argument('--crear-pedido', action='store_true',
                            help='Crea una compra nueva y activa el notificador configurado.')

    def handle(self, *args, **options):
        with transaction.atomic():
            user, created = get_user_model().objects.get_or_create(
                username='volt_demo', defaults={'email': 'volt_demo@example.com'})
            if created:
                user.set_password('VoltDemo2026!')
                user.save(update_fields=['password'])
            address, _ = Address.objects.get_or_create(
                user=user, street='Calle Demo 123',
                defaults={'city': 'Bogotá', 'state': 'Bogotá D.C.', 'zip_code': '110111',
                          'country': 'Colombia', 'is_default': not user.addresses.exists()})
            products = []
            count = 0
            for category_name, name, description, price, stock in PRODUCTS:
                category, _ = Category.objects.get_or_create(name=category_name)
                product, new = Product.objects.get_or_create(
                    name=name, category=category,
                    defaults={'description': description, 'price': Decimal(price), 'stock': stock})
                products.append(product)
                count += int(new)
            cart, _ = Cart.objects.get_or_create(user=user)
            for product, quantity in ((products[0], 2), (products[4], 1), (products[11], 1)):
                CartItem.objects.get_or_create(cart=cart, product=product,
                                              defaults={'quantity': quantity})
        self.stdout.write(self.style.SUCCESS(f'Catálogo listo: {count} productos nuevos; 12 de demostración.'))
        self.stdout.write('Precios de ejemplo en COP. No se restablece el inventario existente.')
        self.stdout.write('Usuario: volt_demo (comprador sin acceso al administrador).')
        self.stdout.write('Contraseña inicial: VoltDemo2026!' if created else
                          'Usuario existente: se conserva su contraseña.')
        self.stdout.write(f'Carrito: {cart.items.count()} líneas; total: ${cart.total():,.2f} COP.')
        if options['crear_pedido']:
            try:
                order = OrderService().create_order(user, shipping_address=address)
            except OrderServiceError as exc:
                raise CommandError(f'No se pudo crear el pedido: {exc}') from exc
            self.stdout.write(self.style.SUCCESS(f'Pedido #{order.pk} creado; total: ${order.total:,.2f} COP.'))
            self.stdout.write(f'Notificador configurado: {settings.NOTIFICATIONS_BACKEND}.')
            self.stdout.write('Se ejecutó el flujo de notificación. Un pedido creado no garantiza entrega; revisa los logs.')
        else:
            self.stdout.write('Para comprar y activar la notificación: python manage.py cargar_demo --crear-pedido')
