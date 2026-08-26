from decimal import Decimal

from rest_framework import serializers

from .models import Address, Cart, CartItem, Category, Order, OrderItem, Product


class CreateOrderInputSerializer(serializers.Serializer):
    """Serializer de entrada para mantener un contrato explicito del endpoint."""
    shipping_address_id = serializers.IntegerField(required=False, allow_null=True)
    shipping_address = serializers.IntegerField(required=False, allow_null=True)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'description')


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'description', 'price', 'stock', 'category')


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('id', 'street', 'city', 'state', 'zip_code', 'country', 'is_default')
        read_only_fields = ('id',)


class AddCartItemInputSerializer(serializers.Serializer):
    """Serializer de entrada: mantiene el contrato explícito de agregar al carrito."""
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'quantity', 'subtotal')


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total')


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('product_id', 'product_name', 'quantity', 'price', 'subtotal')


class OrderSerializer(serializers.ModelSerializer):
    shipping_address = AddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'status', 'total', 'created_at', 'shipping_address', 'items')
