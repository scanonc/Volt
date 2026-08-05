from django.urls import path

from .views import CreateOrderView

app_name = 'Volt'

urlpatterns = [
    path('orders/', CreateOrderView.as_view(), name='create-order'),
]
