from rest_framework import serializers
from .models import Category
from app.dicts import DeleteStatus


class CategoryListSerializer(serializers.ModelSerializer):
    """
    品类列表序列化器（用于 GET 响应）
    只返回前端需要的字段，隐藏 is_delete 等内部字段
    """

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'parent_id', 'create_time']


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
        """跨字段校验：防止自身引用和循环引用"""
        parent = attrs.get('parent')
        instance = self.instance  # 创建时为 None，修改时为当前品类对象

        if parent and instance:
            # 不能将自身设为父级
            if parent.id == instance.id:
                raise serializers.ValidationError({'parent': '不能将自身设为父级品类'})
            # 不能将子孙节点设为父级（会造成循环引用）
            if self._is_descendant(instance, parent):
                raise serializers.ValidationError({'parent': '不能将子级品类设为父级，会造成循环引用'})

        return attrs

    def _is_descendant(self, instance, target):
        """
        递归检查 target 是否是 instance 的子孙节点
        :param instance: 当前品类
        :param target:   待检查的目标品类
        """
        children = Category.objects.filter(parent=instance, is_delete=False)
        for child in children:
            if child.id == target.id or self._is_descendant(child, target):
                return True
        return False
