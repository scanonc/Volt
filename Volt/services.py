from django.db import transaction

from .domain.builders import OrderBuilder
from .infra.factory import NotificationFactory
from .models import Cart


class OrderService:
    def create_order(self, user):
        cart = Cart.objects.filter(user=user).first()
        if cart is None:
            raise ValueError('User does not have a cart.')

        cart_items = list(cart.items.select_related('product'))
        if not cart_items:
            raise ValueError('Cart is empty.')

        with transaction.atomic():
            order, order_items = (
                OrderBuilder()
                .for_user(user)
                .with_items(cart_items)
                .build()
            )
            order.save()

            for order_item in order_items:
                order_item.order = order
                order_item.save()

            cart.items.all().delete()

        notifier = NotificationFactory.create()
        notifier.send_confirmation(order)
        return order
