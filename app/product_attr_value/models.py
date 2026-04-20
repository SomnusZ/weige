from django.db import models
from app.product.models import Product
from app.category_attr_def.models import CategoryAttrDef
from app.dicts import DeleteStatus


class ProductAttrValue(models.Model):
    """
    商品属性值表（EAV 模式核心表）
    每条记录对应一个商品的一个属性值
    通过 value_type 分列存储，避免全部用 str 带来的类型问题
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,               # 商品删除时，属性值一并删除
        related_name='attr_values',             # 反向查询：product.attr_values.all()
        verbose_name='所属商品'
    )

    attr_def = models.ForeignKey(
        CategoryAttrDef,
        on_delete=models.CASCADE,               # 属性定义删除时，属性值一并删除
        related_name='attr_values',             # 反向查询：attr_def.attr_values.all()
        verbose_name='属性定义'
    )

    # 分类型存储，根据 attr_def.value_type 决定使用哪个字段
    value_str   = models.CharField(max_length=500, null=True, blank=True, verbose_name='文本值')
    value_int   = models.IntegerField(null=True, blank=True, verbose_name='整数值')
    value_float = models.FloatField(null=True, blank=True, verbose_name='小数值')
    value_bool  = models.BooleanField(null=True, blank=True, verbose_name='布尔值')

    create_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    is_delete = models.BooleanField(
        default=DeleteStatus.NORMAL,            # 默认未删除
        verbose_name='是否删除'
    )

    class Meta:
        db_table = 'product_attr_value'         # 指定数据库表名
        verbose_name = '商品属性值'
        verbose_name_plural = '商品属性值'
        ordering = ['id']
        # 同一商品下同一属性定义只能有一条记录
        unique_together = [('product', 'attr_def')]

    def __str__(self):
        return f'{self.product.product_name} - {self.attr_def.attr_name}'
