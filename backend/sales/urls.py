from rest_framework.routers import DefaultRouter

from sales import views

router = DefaultRouter()
router.register(r'sales', views.SaleViewSet, basename='sale')
router.register(r'debts', views.CustomerDebtViewSet, basename='customer-debt')
router.register(r'debt-payments', views.DebtPaymentViewSet, basename='debt-payment')
router.register(r'sales-summary', views.SalesSummaryViewSet, basename='sales-summary')

app_name = 'sales'

urlpatterns = router.urls
