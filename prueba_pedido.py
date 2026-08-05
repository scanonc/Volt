# prueba_pedido.py
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.contrib.auth import get_user_model
from Volt.models import Cart, Product, CartItem
from Volt.services import OrderService

user = get_user_model().objects.get(username='sebas')
cart = Cart.objects.get(user=user)

for name in ['camisas', 'pantalones', 'zapatos']:
    product = Product.objects.get(name=name)
    CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 1})

order = OrderService().create_order(user)
print('Pedido creado:', order.id)
print('Total:', order.total)
print('Estado:', order.status)