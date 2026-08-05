from decimal import Decimal

from ..models import Order, OrderItem


class OrderBuilder:
    def __init__(self):
        self.user = None
        self.cart_items = []

    def for_user(self, user):
        self.user = user
        return self

    def with_items(self, cart_items):
        self.cart_items = list(cart_items)
        return self

    def build(self):
        if not self.user:
            raise ValueError('A user is required to create an order.')
        if not self.cart_items:
            raise ValueError('At least one product is required to create an order.')

        order = Order(user=self.user, status=Order.Status.PENDING, total=Decimal('0'))
        order.total = sum(item.subtotal() for item in self.cart_items)

        order_items = []
        for cart_item in self.cart_items:
            order_items.append(
                OrderItem(
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price,
                    subtotal=cart_item.subtotal(),
                )
            )

        return order, order_items
