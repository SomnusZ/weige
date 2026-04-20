from rest_framework import serializers
from .models import CategoryAttrDef
from app.dicts import DeleteStatus


class CategoryAttrDefValidationMixin:
    """
    品类属性定义字段校验 Mixin
    提取 Create 和 Update 序列化器的公共校验逻辑，避免重复代码
    """

    def validate_attr_name(self, value):
        """属性名称：去除首尾空格后不能为空"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError('属性名称不能为空')
        return value


class CategoryAttrDefCreateSerializer(CategoryAttrDefValidationMixin, serializers.ModelSerializer):
    """
    属性定义创建序列化器（用于 POST 请求）
    category 和 value_type 创建后不可修改，与 update 序列化器分开
    """

    class Meta:
        model = CategoryAttrDef
        fields = ['category', 'attr_name', 'value_type', 'is_required']

    def validate_category(self, value):
        """所属品类：必须存在且未被逻辑删除"""
        if value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('所属品类不存在或已被删除')
        return value
    # value_type 无需手动校验，模型已配置 choices，DRF 自动验证合法性


class CategoryAttrDefUpdateSerializer(CategoryAttrDefValidationMixin, serializers.ModelSerializer):
    """
    属性定义修改序列化器（用于 PATCH 请求）
    只允许修改 attr_name 和 is_required
    category 和 value_type 创建后不可变更，防止破坏已有商品属性数据
    """

    class Meta:
        model = CategoryAttrDef
        fields = ['attr_name', 'is_required']


class CategoryAttrDefListSerializer(serializers.ModelSerializer):
    """
    属性定义列表序列化器（用于 GET 响应）
    只返回前端需要的字段
    """

    class Meta:
        model = CategoryAttrDef
        fields = ['id', 'category_id', 'attr_name', 'value_type', 'is_required', 'create_time']
