from rest_framework import serializers
from .models import Category
from app.dicts import DeleteStatus
# 延迟导入，避免循环引用（category_attr_def 和 product 均依赖 category）
from app.category_attr_def.models import CategoryAttrDef
from app.product.models import Product


class CategoryListSerializer(serializers.ModelSerializer):
    """
    品类列表序列化器（用于 GET 响应）
    parent_name 为动态计算字段，不存入数据库，始终与父级名称保持一致
    """
    # 动态计算父级名称，避免数据库冗余字段
    parent_name = serializers.SerializerMethodField()

    def get_parent_name(self, obj):
        return obj.parent.category_name if obj.parent else None

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'parent_id', 'parent_name', 'create_time']


class CategoryWriteSerializer(serializers.ModelSerializer):
    """
    品类写入序列化器（用于 POST 创建 和 PATCH 修改）
    只接收 category_name 和 parent，其他字段由后端自动处理
    """

    class Meta:
        model = Category
        fields = ['category_name', 'parent']

    def validate_category_name(self, value):
        """校验品类名称：去除首尾空格后不能为空"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError('品类名称不能为空')
        return value

    def validate_parent(self, value):
        """校验父级品类：必须存在且未被逻辑删除"""
        if value is not None and value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('父级品类不存在或已被删除')
        return value

    def validate(self, attrs):
        """跨字段校验：同级名称唯一、防止自身引用和循环引用"""
        parent   = attrs.get('parent')
        name     = attrs.get('category_name')
        instance = self.instance  # 创建时为 None，修改时为当前品类对象

        # 名称全局唯一校验：所有品类中不能有重名
        if name:
            qs = Category.objects.filter(
                category_name=name,
                is_delete=DeleteStatus.NORMAL
            )
            if instance:
                qs = qs.exclude(id=instance.id)  # 修改时排除自身
            if qs.exists():
                raise serializers.ValidationError({'category_name': '品类名称已存在'})

        # ────────────────────────────────────────────────────
        # 叶子节点保护：防止将已有属性定义或商品的品类再挂子品类
        #
        # 背景：本系统规定属性定义和商品只能挂在叶子节点品类上。
        #       一旦某品类已配置了属性定义或已有商品，说明它当前
        #       承担着"叶子节点"的职责。若此时允许为其新增子品类，
        #       该品类将从叶子变为中间节点，导致属性定义和商品数据
        #       与叶子节点规则产生矛盾，破坏数据一致性。
        #
        # 正确操作顺序：如需细化层级，应先逐一删除该品类下的
        #               属性定义和商品，再为其新增子品类。
        # ────────────────────────────────────────────────────
        if parent:
            has_attr_defs = CategoryAttrDef.objects.filter(
                category=parent, is_delete=DeleteStatus.NORMAL
            ).exists()
            has_products = Product.objects.filter(
                category=parent, is_delete=DeleteStatus.NORMAL
            ).exists()
            if has_attr_defs or has_products:
                raise serializers.ValidationError(
                    {'parent': '该品类已配置属性定义或已有商品，不能再添加子品类。如需细化层级，请先删除其属性定义和商品'}
                )

        if parent and instance:
            # 不能将自身设为父级
            if parent.id == instance.id:
                raise serializers.ValidationError({'parent': '不能将自身设为父级品类'})
            # 不能将子孙节点设为父级（会造成循环引用）
            if self._is_descendant(instance, parent):
                raise serializers.ValidationError({'parent': '不能将子级品类设为父级，会造成循环引用'})

        return attrs

    def _is_descendant(self, instance, target):
        """递归检查 target 是否是 instance 的子孙节点"""
        children = Category.objects.filter(parent=instance, is_delete=DeleteStatus.NORMAL)
        for child in children:
            if child.id == target.id or self._is_descendant(child, target):
                return True
        return False
