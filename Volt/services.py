from django.db import transaction

from .domain.builders import OrderBuilder
from .infra.factory import NotificationFactory
from .models import Cart, Product


class OrderServiceError(Exception):
    pass


class CartNotFoundError(OrderServiceError):
    pass


class EmptyCartError(OrderServiceError):
    pass


class InsufficientStockError(OrderServiceError):
    pass


class OrderService:
    def create_order(self, user):
        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(user=user).first()
            if cart is None:
                raise CartNotFoundError('User does not have a cart.')

            cart_items = list(cart.items.select_related('product').select_for_update())
            if not cart_items:
                raise EmptyCartError('Cart is empty.')

            requested_by_product = {}
            for cart_item in cart_items:
                requested_by_product[cart_item.product_id] = (
                    requested_by_product.get(cart_item.product_id, 0) + cart_item.quantity
                )

            products = Product.objects.select_for_update().filter(id__in=requested_by_product.keys())
            products_by_id = {product.id: product for product in products}

            for product_id, requested_quantity in requested_by_product.items():
                product = products_by_id[product_id]
                if product.stock < requested_quantity:
                    raise InsufficientStockError(
                        f'Insufficient stock for product "{product.name}". '
                        f'Requested: {requested_quantity}, available: {product.stock}.'
                    )

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

            for product_id, requested_quantity in requested_by_product.items():
                product = products_by_id[product_id]
                product.stock -= requested_quantity
                product.save(update_fields=['stock'])

            cart.items.all().delete()

        notifier = NotificationFactory.create()
        notifier.send_confirmation(order)
        return order
