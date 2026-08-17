from django.urls import path

from .views import (
    CategoryListView,
    CreateOrderView,
    ProductDetailView,
    ProductListView,
)

app_name = 'Volt'

urlpatterns = [
    path('orders/', CreateOrderView.as_view(), name='create-order'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
