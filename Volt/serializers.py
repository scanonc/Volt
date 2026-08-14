from rest_framework import serializers

from .models import Order, OrderItem


class CreateOrderInputSerializer(serializers.Serializer):
    """Serializer de entrada para mantener un contrato explicito del endpoint."""


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('product_id', 'product_name', 'quantity', 'price', 'subtotal')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'status', 'total', 'created_at', 'items')
