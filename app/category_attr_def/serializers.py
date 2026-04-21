from rest_framework import serializers
from .models import CategoryAttrDef
from app.category.models import Category
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
        """
        所属品类校验：
        1. 品类必须存在且未被逻辑删除
        2. 品类必须是叶子节点（无子品类）
           背景：属性定义描述的是"某类商品有哪些属性"，属于最小粒度的
                品类模板。只有叶子节点才是最终承载商品的品类，在此配置
                属性定义才有实际意义。非叶子节点是分类导航层级，不应
                直接挂载属性定义。
        """
        if value.is_delete == DeleteStatus.DELETED:
            raise serializers.ValidationError('所属品类不存在或已被删除')
        # 检查是否为叶子节点：若存在未删除的子品类，则为非叶子节点，拒绝操作
        if Category.objects.filter(parent=value, is_delete=DeleteStatus.NORMAL).exists():
            raise serializers.ValidationError('只能为末级品类配置属性定义（该品类下还有子品类）')
        return value
    # value_type 无需手动校验，模型已配置 choices，DRF 自动验证合法性

    def validate(self, attrs):
        """
        跨字段校验：is_required=True 时，检查品类下是否已有商品

        背景：
          若某品类已有商品，说明这些商品是在没有该属性定义的情况下创建的，
          数据库中没有对应的属性值记录。此时若新增一个 is_required=True
          的属性定义，现有商品将立即违反"必填"约束，造成数据不一致。
          非必填（is_required=False）的属性定义可以随时新增，历史商品
          只是缺省该属性，属于正常的可选字段扩展。

        正确操作顺序：
          如需为有商品的品类新增必填属性，应先将现有商品全部删除，
          配置好属性定义后，再重新录入商品并补全属性值。
        """
        # 延迟导入，避免与 app.product 形成循环引用（product → category_attr_def → product）
        from app.product.models import Product

        is_required = attrs.get('is_required', False)
        category    = attrs.get('category')

        if is_required and category:
            if Product.objects.filter(category=category, is_delete=DeleteStatus.NORMAL).exists():
                raise serializers.ValidationError({
                    'is_required': (
                        '该品类下已有商品，不能新增必填属性定义。'
                        '现有商品没有该属性的记录，会立即违反必填约束。'
                        '请将 is_required 改为 False，或先删除该品类下所有商品再操作。'
                    )
                })
        return attrs


class CategoryAttrDefUpdateSerializer(CategoryAttrDefValidationMixin, serializers.ModelSerializer):
    """
    属性定义修改序列化器（用于 PATCH 请求）
    只允许修改 attr_name 和 is_required
    category 和 value_type 创建后不可变更，防止破坏已有商品属性数据
    """

    class Meta:
        model = CategoryAttrDef
        fields = ['attr_name', 'is_required']

    def validate(self, attrs):
        """
        跨字段校验：将 is_required 由 False 改为 True 时，检查品类下是否有商品未填写该属性值

        背景：
          与新增必填属性定义不同，此处属性定义已存在（原本非必填），
          品类下的部分商品可能已经填写了该属性值。因此不能像 Create 那样
          "只要有商品就拦截"，而应精确检查：是否有商品**缺少**该属性值记录。

          - 若所有商品都已填写 → 安全，允许改为必填
          - 若存在未填写的商品 → 改为必填会立即违反约束，拒绝操作

        正确操作顺序：
          先在商品属性值页面为所有商品补填该属性值，再回来将其设为必填。

        注意：
          - 只在 is_required 被**明确由 False 改为 True** 时触发检查
          - 若本次未修改 is_required，或原本已是 True，则跳过
        """
        new_is_required = attrs.get('is_required')

        # 仅在"False → True"变更时才需要检查
        if new_is_required is True and self.instance.is_required is False:
            # 延迟导入，避免循环引用：
            #   product_attr_value.models → category_attr_def.models（ForeignKey）
            #   category_attr_def.serializers → product_attr_value.models（此处）
            from app.product.models import Product
            from app.product_attr_value.models import ProductAttrValue

            category = self.instance.category

            products_qs = Product.objects.filter(
                category=category,
                is_delete=DeleteStatus.NORMAL
            )

            if products_qs.exists():
                # 已为该属性定义填写了值的商品 ID 集合
                filled_ids = ProductAttrValue.objects.filter(
                    attr_def=self.instance,
                    is_delete=DeleteStatus.NORMAL
                ).values_list('product_id', flat=True)

                # 缺少该属性值的商品数量
                unfilled_count = products_qs.exclude(id__in=filled_ids).count()

                if unfilled_count > 0:
                    raise serializers.ValidationError({
                        'is_required': (
                            f'该品类下有 {unfilled_count} 件商品尚未填写此属性值，'
                            '将其改为必填会立即违反约束。'
                            '请先为这些商品补填该属性值后再操作；'
                            '或删除此品类下的所有商品，重新配置必填属性后再录入商品。'
                        )
                    })

        return attrs


class CategoryAttrDefListSerializer(serializers.ModelSerializer):
    """
    属性定义列表序列化器（用于 GET 响应）
    只返回前端需要的字段
    """

    class Meta:
        model = CategoryAttrDef
        fields = ['id', 'category_id', 'attr_name', 'value_type', 'is_required', 'create_time']
