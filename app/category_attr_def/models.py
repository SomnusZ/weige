from django.db import models
from app.category.models import Category
from app.dicts import DeleteStatus, AttrValueType


class CategoryAttrDef(models.Model):
    """
    品类属性定义表
    定义每个品类下有哪些个性化属性、属性类型及是否必填
    作为商品动态属性（EAV）的模板
    """

    # value_type 可选值，来自 AttrValueType 字典项
    VALUE_TYPE_CHOICES = [
        (AttrValueType.STR,   '文本'),
        (AttrValueType.INT,   '整数'),
        (AttrValueType.FLOAT, '小数'),
        (AttrValueType.BOOL,  '布尔'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,           # 品类删除时，其属性定义一并删除
        related_name='attr_defs',           # 反向查询：category.attr_defs.all()
        verbose_name='所属品类'
    )

    attr_name = models.CharField(
        max_length=100,
        verbose_name='属性名称'             # 如：颜色、袖长、材质
    )

    value_type = models.CharField(
        max_length=10,
        choices=VALUE_TYPE_CHOICES,
        default=AttrValueType.STR,          # 默认文本类型
        verbose_name='属性值类型'
    )

    is_required = models.BooleanField(
        default=False,                      # 默认非必填
        verbose_name='是否必填'
    )

    create_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    is_delete = models.BooleanField(
        default=DeleteStatus.NORMAL,        # 默认未删除
        verbose_name='是否删除'
    )

    class Meta:
        db_table = 'category_attr_def'      # 指定数据库表名
        verbose_name = '品类属性定义'
        verbose_name_plural = '品类属性定义'
        ordering = ['id']
        # 同一品类下属性名不允许重复
        unique_together = [('category', 'attr_name')]

    def __str__(self):
        return f'{self.category.category_name} - {self.attr_name}'
