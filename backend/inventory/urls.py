from rest_framework.routers import DefaultRouter

from inventory import views

router = DefaultRouter()
router.register(r'stock-movements', views.StockMovementViewSet, basename='stock-movement')
router.register(r'goods-entries', views.GoodsEntryViewSet, basename='goods-entry')
router.register(r'exit-notes', views.ExitNoteViewSet, basename='exit-note')

app_name = 'inventory'

urlpatterns = router.urls
