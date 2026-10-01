import logging

from django.db.models import Count, F, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from catalog.models import Category, Product, ProductImage
from catalog.serializers import (
    UNIT_CHOICES,
    CategorySerializer,
    ProductImageSerializer,
    ProductSerializer,
    ProductWriteSerializer,
)
from catalog.surcharge import SURCHARGE_PRESET_VALUES
from core.permissions import CanAccessResource

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
    """Categories with their shared surcharge.

    A category is referenced by products through a PROTECT foreign key, so
    deleting one that still has articles is refused by the database rather than
    silently orphaning them.
    """

    permission_model = Category
    permission_classes = [CanAccessResource]
    serializer_class = CategorySerializer
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        queryset = Category.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        )
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        return queryset

    @action(detail=False, methods=['get'], url_path='surcharge-presets')
    def surcharge_presets(self, request):
        """Quick-pick percentages offered by the till."""
        return Response({'values': SURCHARGE_PRESET_VALUES})

    def perform_destroy(self, instance):
        if instance.products.exists():
            raise ValidationError(
                {'detail': 'La categoría tiene artículos asignados. Quítaselos antes de eliminarla.'}
            )
        instance.delete()


class ProductViewSet(viewsets.ModelViewSet):
    permission_model = Product
    permission_classes = [CanAccessResource]
    filterset_fields = ['is_active', 'unit_of_measure', 'brand', 'category']
    search_fields = ['name', 'brand', 'code', 'barcode']
    ordering_fields = ['name', 'code', 'price_usd', 'cost_usd', 'stock', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ProductWriteSerializer
        return ProductSerializer

    def create(self, request, *args, **kwargs):
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        product = write_serializer.save()
        return Response(
            ProductSerializer(product, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        write_serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs['partial'])
        write_serializer.is_valid(raise_exception=True)
        product = write_serializer.save()
        return Response(ProductSerializer(product, context=self.get_serializer_context()).data)

    def get_queryset(self):
        queryset = Product.objects.select_related('category')
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        if self.request.query_params.get('low_stock') == 'true':
            queryset = queryset.filter(stock__lte=F('units_per_package'))
        if self.request.query_params.get('out_of_stock') == 'true':
            queryset = queryset.filter(stock=0)
        return queryset

    @action(detail=False, methods=['get'], url_path='unit-choices')
    def unit_choices(self, request):
        return Response(UNIT_CHOICES)

    @action(detail=False, methods=['get'])
    def barcode_lookup(self, request):
        code = (request.query_params.get('code') or '').strip()
        if not code:
            return Response({'detail': 'Envíe el parámetro code.'}, status=400)
        product = Product.objects.filter(barcode=code).first()
        if product is None and code.isdigit():
            product = Product.objects.filter(code=code).first()
        if product is None:
            return Response({'detail': 'Artículo no encontrado.'}, status=404)
        return Response(ProductSerializer(product, context={'request': request}).data)


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.select_related('product')
    serializer_class = ProductImageSerializer
    permission_model = ProductImage
    permission_classes = [CanAccessResource]
    action_permissions = {'set_primary': 'catalog.change_productimage'}
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['product', 'is_primary']
    ordering_fields = ['sort_order', 'created_at']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'create':
            context['product'] = _resolve_product(self.request.data.get('product'))
        return context

    def perform_create(self, serializer):
        product = _resolve_product(self.request.data.get('product'))
        if product is None:
            raise ValidationError({'product': 'Producto inválido.'})
        serializer.save(product=product)

    def perform_destroy(self, instance):
        # The row must go even if the file cannot be unlinked: on Windows a
        # scanner or a second handle can hold a transient lock, and a 500 here
        # would leave the user unable to remove the photo at all. The orphan
        # file is harmless; a stuck record is not.
        for field in (instance.image, instance.thumbnail):
            if not field:
                continue
            try:
                field.delete(save=False)
            except OSError as error:
                logger.warning('No se pudo borrar el archivo %s: %s', field.name, error)
        instance.delete()

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        image = self.get_object()
        ProductImage.objects.filter(product_id=image.product_id, is_primary=True).exclude(
            pk=image.pk
        ).update(is_primary=False)
        ProductImage.objects.filter(pk=image.pk).update(is_primary=True)
        image.refresh_from_db()
        return Response(ProductImageSerializer(image, context=self.get_serializer_context()).data)


def _resolve_product(reference):
    if isinstance(reference, Product):
        return reference
    try:
        pk = int(reference)
    except (TypeError, ValueError):
        return None
    return Product.objects.filter(pk=pk).first()
