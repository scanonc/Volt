import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Address, Category, Product
from .serializers import (
    AddCartItemInputSerializer,
    AddressSerializer,
    CartSerializer,
    CategorySerializer,
    CreateOrderInputSerializer,
    OrderSerializer,
    ProductSerializer,
)
from .services import (
    AddressNotFoundError,
    CartItemNotFoundError,
    CartNotFoundError,
    CartService,
    EmptyCartError,
    InsufficientStockError,
    InvalidAddressError,
    OrderService,
    ProductNotFoundError,
)


def notification_dashboard(request):
    return render(request, 'dashboard/index.html', {'csrf_token': get_token(request)})


def notification_health(request):
    health_url = settings.NOTIFICATIONS_URL.replace('/api/v2/notifications/', '/health/')
    try:
        with urlopen(health_url, timeout=2) as response:
            return JsonResponse(json.loads(response.read()), status=response.status)
    except (HTTPError, URLError, OSError, ValueError):
        return JsonResponse({'status': 'offline', 'service': 'notifications'}, status=503)


def send_notification(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({'error': {'message': 'JSON inválido.'}}, status=400)

    try:
        api_request = Request(
            settings.NOTIFICATIONS_URL,
            data=json.dumps(payload).encode('utf-8'),
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': settings.NOTIFICATIONS_API_KEY,
            },
        )
        with urlopen(api_request, timeout=settings.NOTIFICATIONS_TIMEOUT) as response:
            return JsonResponse(json.loads(response.read()), status=response.status)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read())
        except (TypeError, ValueError):
            error = {'error': {'message': 'El servicio rechazó la solicitud.'}}
        return JsonResponse(error, status=exc.code)
    except (URLError, OSError, ValueError):
        return JsonResponse(
            {'error': {'message': 'El servicio de notificaciones no está disponible.'}},
            status=503,
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

        shipping_address_id = (
            input_serializer.validated_data.get('shipping_address_id')
            or input_serializer.validated_data.get('shipping_address')
        )

        try:
            order = OrderService().create_order(request.user, shipping_address_id=shipping_address_id)
        except CartNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except EmptyCartError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except InsufficientStockError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
        except AddressNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InvalidAddressError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output_serializer = OrderSerializer(order)

        return Response({
            'message': 'Order created successfully.',
            'order': output_serializer.data,
        }, status=status.HTTP_201_CREATED)


class AddressListView(APIView):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        addresses = Address.objects.filter(user=request.user)
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = AddressSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        address = serializer.save(user=request.user)
        return Response(AddressSerializer(address).data, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    def get(self, request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        address = Address.objects.filter(pk=pk, user=request.user).first()
        if address is None:
            return Response({'error': 'Address not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AddressSerializer(address)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartView(APIView):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        cart = CartService().get_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemListView(APIView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        input_serializer = AddCartItemInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response({'errors': input_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            CartService().add_item(
                request.user,
                product_id=input_serializer.validated_data['product_id'],
                quantity=input_serializer.validated_data['quantity'],
            )
        except ProductNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InsufficientStockError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)

        cart = CartService().get_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    def delete(self, request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            CartService().remove_item(request.user, pk)
        except CartItemNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


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
