from rest_framework import serializers
from .models import ProductAttrValue
from app.dicts import DeleteStatus, ATTR_TYPE_FIELD_MAP


def validate_value_by_type(attrs, attr_def):
    """
    公共校验函数：根据属性定义的 value_type，校验对应值字段非空，其余字段强制清空
    Create 和 Update 序列化器共用此逻辑
    :param attrs:    序列化器 validate() 传入的字段字典
    :param attr_def: 属性定义对象，提供 value_type 和 is_required
    """
    expected_field = ATTR_TYPE_FIELD_MAP.get(attr_def.value_type)

    # 必填属性校验
    if attr_def.is_required and attrs.get(expected_field) is None:
        raise serializers.ValidationError({expected_field: '该属性为必填项，不能为空'})

    # 其余值字段强制清空，保持数据干净
    for field in ATTR_TYPE_FIELD_MAP.values():
        if field != expected_field:
            attrs[field] = None


class ProductAttrValueCreateSerializer(serializers.ModelSerializer):
    """
    商品属性值创建序列化器（用于 POST 请求）
    product 和 attr_def 创建后不可修改，与 update 序列化器分开
    """

    class Meta:
        model = ProductAttrValue
        fields = ['product', 'attr_def', 'value_str', 'value_int', 'value_float', 'value_bool']

    def validate_product(self, value):
        """所属商品：必须存在且未被逻辑删除"""
        if value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('所属商品不存在或已被删除')
        return value

    def validate_attr_def(self, value):
        """属性定义：必须存在且未被逻辑删除"""
        if value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('属性定义不存在或已被删除')
        return value

    def validate(self, attrs):
        """
        跨字段校验：
        1. 属性定义必须属于该商品的品类
        2. 根据 value_type 校验对应值字段非空，其余字段清空
        """
        product  = attrs.get('product')
        attr_def = attrs.get('attr_def')

        # 属性定义必须属于该商品的品类
        if product and attr_def and attr_def.category_id != product.category_id:
            raise serializers.ValidationError({'attr_def': '该属性定义不属于此商品的品类'})

        validate_value_by_type(attrs, attr_def)
        return attrs


class ProductAttrValueUpdateSerializer(serializers.ModelSerializer):
    """
    商品属性值修改序列化器（用于 PATCH 请求）
    不允许修改 product 和 attr_def，只允许修改值字段
    """

    class Meta:
        model = ProductAttrValue
        fields = ['value_str', 'value_int', 'value_float', 'value_bool']

    def validate(self, attrs):
        """根据当前记录的 attr_def.value_type 校验对应值字段"""
        validate_value_by_type(attrs, self.instance.attr_def)
        return attrs


class ProductAttrValueListSerializer(serializers.ModelSerializer):
    """
    商品属性值列表序列化器（用于 GET 响应）
    只返回前端需要的字段
    """

    class Meta:
        model = ProductAttrValue
        fields = ['id', 'product_id', 'attr_def_id',
                  'value_str', 'value_int', 'value_float', 'value_bool', 'create_time']
