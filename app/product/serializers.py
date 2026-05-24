from rest_framework import serializers
from .models import Product, ProductImage
from app.category.models import Category
from app.dicts import DeleteStatus


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = ProductImage
        fields = ['id', 'image_url', 'is_primary', 'sort_order']


class ProductValidationMixin:
    def validate_product_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('商品名称不能为空')
        return value

    def validate_product_price(self, value):
        if value < 0:
            raise serializers.ValidationError('商品价格不能为负数')
        return value

    def validate_product_stock(self, value):
        if value < 0:
            raise serializers.ValidationError('库存数量不能为负数')
        return value


class ProductCreateSerializer(ProductValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['product_name', 'category', 'product_price', 'product_stock']

    def validate_category(self, value):
        if value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('所属品类不存在或已被删除')
        if Category.objects.filter(parent=value, is_delete=DeleteStatus.NORMAL).exists():
            raise serializers.ValidationError('只能选择末级品类（该品类下还有子品类）')
        return value


class ProductUpdateSerializer(ProductValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['product_name', 'product_price', 'product_stock']


def _get_primary_image_url(obj, request):
    images = getattr(obj, 'prefetched_images', [])
    primary = next((img for img in images if img.is_primary and not img.is_delete), None)
    if primary is None and images:
        primary = images[0]
    if not primary:
        return None
    url = primary.image.url
    return request.build_absolute_uri(url) if request else url


class ProductListSerializer(serializers.ModelSerializer):
    primary_image_url = serializers.SerializerMethodField()

    def get_primary_image_url(self, obj):
        return _get_primary_image_url(obj, self.context.get('request'))

    class Meta:
        model = Product
        fields = ['id', 'product_name', 'category_id', 'product_price',
                  'primary_image_url', 'product_stock', 'create_time']


class ProductPublicSerializer(serializers.ModelSerializer):
    category_name     = serializers.CharField(source='category.category_name', read_only=True)
    primary_image_url = serializers.SerializerMethodField()
    images            = serializers.SerializerMethodField()
    attrs             = serializers.SerializerMethodField()

    def get_primary_image_url(self, obj):
        return _get_primary_image_url(obj, self.context.get('request'))

    def get_images(self, obj):
        request = self.context.get('request')
        result = []
        for img in getattr(obj, 'prefetched_images', []):
            if img.is_delete:
                continue
            url = img.image.url
            result.append({
                'id': img.id,
                'url': request.build_absolute_uri(url) if request else url,
                'is_primary': img.is_primary,
                'sort_order': img.sort_order,
            })
        return result

    def get_attrs(self, obj):
        result = []
        for av in obj.prefetched_attr_values:
            vtype = av.attr_def.value_type
            if vtype == 'str':
                val = av.value_str
            elif vtype == 'int':
                val = str(av.value_int) if av.value_int is not None else None
            elif vtype == 'float':
                val = str(av.value_float) if av.value_float is not None else None
            elif vtype == 'bool':
                val = '是' if av.value_bool else '否'
            else:
                val = None
            if val is not None:
                result.append({'name': av.attr_def.attr_name, 'value': val})
        return result

    class Meta:
        model  = Product
        fields = ['id', 'product_name', 'category_id', 'category_name',
                  'product_price', 'product_stock', 'primary_image_url', 'images', 'attrs']
