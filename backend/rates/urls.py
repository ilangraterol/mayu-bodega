from rest_framework.routers import DefaultRouter

from rates import views

router = DefaultRouter()
router.register(r'rates', views.ExchangeRateViewSet, basename='exchange-rate')

app_name = 'rates'

urlpatterns = router.urls
