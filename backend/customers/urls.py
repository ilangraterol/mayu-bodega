from rest_framework.routers import DefaultRouter

from customers import views

router = DefaultRouter()
router.register(r'customers', views.CustomerViewSet, basename='customer')

app_name = 'customers'

urlpatterns = router.urls
