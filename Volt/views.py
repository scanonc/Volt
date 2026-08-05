from django.http import JsonResponse
from django.views import View

from .services import OrderService


class CreateOrderView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'message': 'Use POST to create an order. Send an authenticated request with the cart populated.',
            'endpoint': '/api/orders/',
        }, status=200)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required.'}, status=401)

        try:
            order = OrderService().create_order(request.user)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({
            'message': 'Order created successfully.',
            'order_id': order.id,
            'status': order.status,
            'total': str(order.total),
        }, status=201)
