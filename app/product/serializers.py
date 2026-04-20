from rest_framework import serializers
from .models import Product
from app.dicts import DeleteStatus


class ProductValidationMixin:
    """
    商品字段校验 Mixin
    提取 Create 和 Update 序列化器的公共校验逻辑，避免重复代码
    """

    def validate_product_name(self, value):
        """商品名称：去除首尾空格后不能为空"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError('商品名称不能为空')
        return value

    def validate_product_price(self, value):
        """商品价格：不能为负数"""
        if value < 0:
            raise serializers.ValidationError('商品价格不能为负数')
        return value

    def validate_product_stock(self, value):
        """库存数量：不能为负数"""
        if value < 0:
            raise serializers.ValidationError('库存数量不能为负数')
        return value


class ProductCreateSerializer(ProductValidationMixin, serializers.ModelSerializer):
    """
    商品创建序列化器（用于 POST 请求）
    category 创建后不可修改，与 update 序列化器分开
    """

    class Meta:
        model = Product
        fields = ['product_name', 'category', 'product_price', 'product_image', 'product_stock']

    def validate_category(self, value):
        """所属品类：必须存在且未被逻辑删除"""
        if value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('所属品类不存在或已被删除')
        return value


class ProductUpdateSerializer(ProductValidationMixin, serializers.ModelSerializer):
    """
    商品修改序列化器（用于 PATCH 请求）
    不允许修改 category，防止品类变更导致动态属性数据混乱
    """

    class Meta:
        model = Product
        fields = ['product_name', 'product_price', 'product_image', 'product_stock']


class ProductListSerializer(serializers.ModelSerializer):
    """
    商品列表序列化器（用于 GET 响应）
    只返回前端需要的字段
    """

    class Meta:
        model = Product
        fields = ['id', 'product_name', 'category_id', 'product_price',
                  'product_image', 'product_stock', 'create_time']
