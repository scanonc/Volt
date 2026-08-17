from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product
from .serializers import (
    CategorySerializer,
    CreateOrderInputSerializer,
    OrderSerializer,
    ProductSerializer,
)
from .services import (
    CartNotFoundError,
    EmptyCartError,
    InsufficientStockError,
    OrderService,
)


class CreateOrderView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({
            'message': 'Use POST to create an order. Send an authenticated request with the cart populated.',
            'endpoint': '/api/orders/',
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        input_serializer = CreateOrderInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response({'errors': input_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = OrderService().create_order(request.user)
        except CartNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except EmptyCartError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except InsufficientStockError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)

        output_serializer = OrderSerializer(order)

        return Response({
            'message': 'Order created successfully.',
            'order': output_serializer.data,
        }, status=status.HTTP_201_CREATED)


class CategoryListView(APIView):
    """Lectura pura del catálogo: no hay lógica de negocio que orquestar."""

    def get(self, request, *args, **kwargs):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductListView(APIView):
    def get(self, request, *args, **kwargs):
        products = Product.objects.select_related('category').all()

        category_id = request.query_params.get('category')
        if category_id is not None:
            products = products.filter(category_id=category_id)

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductDetailView(APIView):
    def get(self, request, pk, *args, **kwargs):
        product = Product.objects.select_related('category').filter(pk=pk).first()
        if product is None:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)
