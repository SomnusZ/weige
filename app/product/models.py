from django.db import models
from app.category.models import Category
from app.dicts import DeleteStatus


class Product(models.Model):
    product_name = models.CharField(max_length=200, verbose_name='商品名称')
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='所属品类'
    )
    product_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='商品价格')
    product_stock = models.IntegerField(default=0, verbose_name='库存数量')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=DeleteStatus.NORMAL, verbose_name='是否删除')

    class Meta:
        db_table = 'product'
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ['-create_time']

    def __str__(self):
        return self.product_name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='所属商品'
    )
    image = models.ImageField(upload_to='products/', verbose_name='图片')
    is_primary = models.BooleanField(default=False, verbose_name='是否主图')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_delete = models.BooleanField(default=DeleteStatus.NORMAL, verbose_name='是否删除')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'product_image'
        verbose_name = '商品图片'
        verbose_name_plural = '商品图片'
        ordering = ['sort_order', 'id']
