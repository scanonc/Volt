from django.urls import path

from .views import (
    AddressDetailView,
    AddressListView,
    CartItemDetailView,
    CartItemListView,
    CartView,
    CategoryListView,
    CreateOrderView,
    ProductDetailView,
    ProductListView,
    notification_dashboard,
    notification_health,
    send_notification,
)

app_name = 'Volt'

urlpatterns = [
    path('', notification_dashboard, name='notification-dashboard'),
    path('notifications/health/', notification_health, name='notification-health'),
    path('notifications/send/', send_notification, name='notification-send'),
    path('addresses/', AddressListView.as_view(), name='address-list'),
    path('addresses/<int:pk>/', AddressDetailView.as_view(), name='address-detail'),
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/items/', CartItemListView.as_view(), name='cart-item-list'),
    path('cart/items/<int:pk>/', CartItemDetailView.as_view(), name='cart-item-detail'),
    path('orders/', CreateOrderView.as_view(), name='create-order'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
