from decimal import Decimal

from rest_framework import serializers

from catalog.image_processing import validate_upload
from catalog.models import UNIT_OF_MEASURE_CHOICES, Product, ProductImage
from core.models import StoreConfig


class ProductImageSerializer(serializers.ModelSerializer):
    # Declared explicitly so DRF builds an `ImageField`, runs the format/size
    # check and hands the upload to `create`. Without it the file never reaches
    # the model and the row is saved with an empty `image`.
    image = serializers.ImageField(write_only=True, required=True, validators=[validate_upload])
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            'id',
            'product',
            'image',
            'url',
            'thumbnail_url',
            'width',
            'height',
            'size_bytes',
            'is_primary',
            'sort_order',
            'created_at',
        ]
        read_only_fields = ['width', 'height', 'size_bytes', 'created_at']

    def get_url(self, obj) -> str:
        return self._absolute(obj.image)

    def get_thumbnail_url(self, obj) -> str:
        return self._absolute(obj.thumbnail or obj.image)

    def _absolute(self, field) -> str:
        if not field:
            return ''
        request = self.context.get('request')
        return request.build_absolute_uri(field.url) if request else field.url

    def create(self, validated_data):
        product = self.context['product']
        # `perform_create` calls `serializer.save(product=...)`, so the key is
        # already in `validated_data`. Passing it again is a duplicate keyword.
        validated_data.pop('product', None)
        # The first photo of a product becomes the primary one, unless the
        # client explicitly asked for another flag.
        is_first = not ProductImage.objects.filter(product=product).exists()
        validated_data['is_primary'] = bool(validated_data.get('is_primary')) or is_first
        return ProductImage.objects.create(product=product, **validated_data)


class ProductSerializer(serializers.ModelSerializer):
    unit_of_measure_display = serializers.CharField(
        source='get_unit_of_measure_display', read_only=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    primary_image_url = serializers.SerializerMethodField()
    can_sell_with_zero_stock = serializers.SerializerMethodField()
    net_units = serializers.DecimalField(source='net_position', max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'code',
            'barcode',
            'name',
            'brand',
            'unit_of_measure',
            'unit_of_measure_display',
            'units_per_package',
            'cost_usd',
            'price_usd',
            'stock',
            'pending_units',
            'net_units',
            'is_active',
            'notes',
            'primary_image_url',
            'can_sell_with_zero_stock',
            'images',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['code', 'stock', 'pending_units', 'created_at', 'updated_at']

    def get_primary_image_url(self, obj) -> str:
        image = obj.primary_image
        if not image:
            return ''
        field = image.thumbnail or image.image
        if not field:
            return ''
        request = self.context.get('request')
        return request.build_absolute_uri(field.url) if request else field.url

    def get_can_sell_with_zero_stock(self, obj) -> bool:
        config = StoreConfig.load()
        return bool(config.allow_zero_stock_sale)

    def validate_barcode(self, value):
        return (value or '').strip() or None

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('El nombre del artículo es obligatorio.')
        return value

    def validate_units_per_package(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Debe ser al menos 1 unidad por empaque.')
        return value

    def validate(self, attrs):
        for field in ('cost_usd', 'price_usd'):
            if field in attrs and attrs[field] is None:
                attrs[field] = Decimal('0.00')
            if field in attrs and attrs[field] < 0:
                raise serializers.ValidationError({field: 'El importe no puede ser negativo.'})
        return attrs


class ProductWriteSerializer(serializers.ModelSerializer):
    """Write payload for the catalogue: it never accepts ``stock``."""

    unit_of_measure_display = serializers.CharField(
        source='get_unit_of_measure_display', read_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id',
            'code',
            'barcode',
            'name',
            'brand',
            'unit_of_measure',
            'unit_of_measure_display',
            'units_per_package',
            'cost_usd',
            'price_usd',
            'is_active',
            'notes',
        ]
        read_only_fields = ['code']

    def validate_barcode(self, value):
        return (value or '').strip() or None

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('El nombre del artículo es obligatorio.')
        return value

    def validate_units_per_package(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Debe ser al menos 1 unidad por empaque.')
        return value

    def validate(self, attrs):
        for field in ('cost_usd', 'price_usd'):
            if field in attrs and attrs[field] is None:
                attrs[field] = Decimal('0.00')
            if field in attrs and attrs[field] < 0:
                raise serializers.ValidationError({field: 'El importe no puede ser negativo.'})
        return attrs


UNIT_CHOICES = [{'value': value, 'label': label} for value, label in UNIT_OF_MEASURE_CHOICES]
