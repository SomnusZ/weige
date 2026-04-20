from django.db import models
from app.category.models import Category
from app.dicts import DeleteStatus


class Product(models.Model):
    """
    商品表
    存储商品的通用属性（所有品类共有的固定字段）
    个性化属性通过 ProductAttribute 表（EAV 模式）单独维护
    """

    product_name = models.CharField(
        max_length=200,
        verbose_name='商品名称'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,           # 品类下有商品时，禁止删除品类
        related_name='products',            # 反向查询：category.products.all()
        verbose_name='所属品类'
    )

    product_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,                   # 最大支持 99999999.99
        verbose_name='商品价格'
    )

    product_image = models.ImageField(
        upload_to='products/',              # 上传至 media/products/ 目录
        null=True,
        blank=True,
        verbose_name='商品图片'
    )

    product_stock = models.IntegerField(
        default=0,
        verbose_name='库存数量'
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
        db_table = 'product'                # 指定数据库表名
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ['-create_time']         # 默认按创建时间倒序

    def __str__(self):
        return self.product_name
