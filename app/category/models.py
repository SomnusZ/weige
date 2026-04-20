from django.db import models
from app.dicts import DeleteStatus


class Category(models.Model):
    """
    商品品类表
    支持无限层级的树形结构，通过 parent 自关联实现
    """

    category_name = models.CharField(
        max_length=100,
        verbose_name='品类名称'
    )

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,      # 父级被删除时，子级 parent 置为 null
        related_name='children',        # 反向查询子级：category.children.all()
        verbose_name='父级品类'
    )

    create_time = models.DateTimeField(
        auto_now_add=True,              # 创建时自动写入当前时间，不可手动修改
        verbose_name='创建时间'
    )

    is_delete = models.BooleanField(
        default=DeleteStatus.NORMAL,    # 默认未删除
        verbose_name='是否删除'
    )

    class Meta:
        db_table = 'category'           # 指定数据库表名
        verbose_name = '商品品类'
        verbose_name_plural = '商品品类'
        ordering = ['id']               # 默认按 id 升序排列

    def __str__(self):
        return self.category_name
