from rest_framework.routers import DefaultRouter

from catalog import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'product-images', views.ProductImageViewSet, basename='product-image')

app_name = 'catalog'

urlpatterns = router.urls
