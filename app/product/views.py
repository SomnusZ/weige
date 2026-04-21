import json

from django.db import transaction
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status

from .models import Product
from .serializers import ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer
from app.category.models import Category
from app.product_attr_value.models import ProductAttrValue
from app.product_attr_value.serializers import (
    ProductAttrValueCreateSerializer,
    ProductAttrValueUpdateSerializer,
)
from app.utils import success_response, error_response
from app.dicts import DeleteStatus


def get_category_ids_with_descendants(category_id):
    """
    递归获取指定品类及其所有子孙品类的 ID 列表

    背景：商品只挂在叶子节点品类上，但用户在筛选时可能选择任意
          层级的品类（如"服装"），此时应返回该品类下所有叶子节点
          品类的商品，而不仅仅是直接属于"服装"的商品。

    实现：深度优先递归向下遍历品类树，收集自身及所有子孙品类的 ID，
          最终通过 category_id__in 一次性查出所有相关商品。

    示例：
        服装(1) → 女装(2) → 大衣(3)
        get_category_ids_with_descendants(1) → [1, 2, 3]
        queryset.filter(category_id__in=[1, 2, 3])
    """
    ids = [category_id]
    children = Category.objects.filter(
        parent_id=category_id,
        is_delete=DeleteStatus.NORMAL
    ).values_list('id', flat=True)
    for child_id in children:
        ids.extend(get_category_ids_with_descendants(child_id))
    return ids


def _parse_attr_values(request_data):
    """
    从 request.data 中解析 attr_values 列表

    兼容两种提交方式：
      - multipart/form-data：attr_values 以 JSON 字符串形式附加（含图片上传时使用）
      - application/json：attr_values 直接为列表
    """
    raw = request_data.get('attr_values', [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raw = []
    return raw if isinstance(raw, list) else []


def _validate_and_collect_attr_value_serializers(product_id, attr_values_raw):
    """
    预校验所有属性值并返回已通过校验的序列化器列表。

    对于每条属性值数据：
      - 若该商品已有对应属性定义的记录 → 使用 Update 序列化器
      - 否则 → 使用 Create 序列化器

    :param product_id:       商品 ID（int）
    :param attr_values_raw:  原始属性值数据列表（来自请求体）
    :return: (av_serializers, errors)
             av_serializers — 校验通过的序列化器列表（可直接 .save()）
             errors         — 校验失败的错误字典 {index: error_detail}
    """
    av_serializers = []
    errors = {}

    for i, av_data in enumerate(attr_values_raw):
        attr_def_id = av_data.get('attr_def')

        # 查找同一商品下同一属性定义的已有记录
        existing = ProductAttrValue.objects.filter(
            product_id=product_id,
            attr_def_id=attr_def_id,
            is_delete=DeleteStatus.NORMAL
        ).first()

        if existing:
            # 已有记录 → 修改模式
            av_ser = ProductAttrValueUpdateSerializer(existing, data=av_data, partial=True)
        else:
            # 无记录 → 创建模式
            data = {**av_data, 'product': product_id}
            av_ser = ProductAttrValueCreateSerializer(data=data)

        if av_ser.is_valid():
            av_serializers.append(av_ser)
        else:
            errors[i] = av_ser.errors

    return av_serializers, errors


class ProductViewSet(ViewSet):
    """
    商品模块视图集
    所有商品相关接口统一在此管理
    """

    def get_product_or_none(self, pk):
        """根据 id 获取未删除的商品，不存在则返回 None"""
        try:
            return Product.objects.get(id=pk, is_delete=DeleteStatus.NORMAL)
        except Product.DoesNotExist:
            return None

    @action(methods=['GET'], detail=False, url_path='dir')
    def dir_product(self, request):
        """
        查询商品列表
        GET /api/products/dir/
        支持按品类筛选：?category_id=<id>（可选）
        """
        queryset = Product.objects.filter(is_delete=DeleteStatus.NORMAL)

        # 可选：按品类筛选（含所有子孙品类）
        category_id = request.query_params.get('category_id')
        if category_id:
            category_ids = get_category_ids_with_descendants(int(category_id))
            queryset = queryset.filter(category_id__in=category_ids)

        serializer = ProductListSerializer(queryset, many=True)
        return success_response(data=serializer.data)

    @action(methods=['POST'], detail=False, url_path='create')
    def create_product(self, request):
        """
        新增商品（同时创建动态属性值）
        POST /api/products/create/

        请求体（multipart/form-data，因需支持图片上传）：
          product_name   — 商品名称（必填）
          category       — 所属品类 ID（必填，末级品类）
          product_price  — 商品价格（必填）
          product_stock  — 库存数量（可选）
          product_image  — 商品图片（可选）
          attr_values    — 属性值列表，JSON 字符串（可选）
                           例：'[{"attr_def":1,"value_str":"红色"},{"attr_def":2,"value_int":42}]'

        处理流程：
          1. 校验商品基本信息
          2. 预校验所有属性值（Create 序列化器）
          3. 在同一事务中保存商品和属性值，任一失败全部回滚
        """
        # ── Step 1：校验商品基本信息 ──
        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message='创建失败', errors=serializer.errors)

        attr_values_raw = _parse_attr_values(request.data)

        with transaction.atomic():
            # ── Step 2：保存商品（先获取 product.id 供属性值引用）──
            product = serializer.save()

            # ── Step 3：预校验属性值 ──
            av_serializers, attr_errors = _validate_and_collect_attr_value_serializers(
                product.id, attr_values_raw
            )

            if attr_errors:
                # 回滚整个事务
                transaction.set_rollback(True)
                return error_response(
                    message='属性值校验失败',
                    errors={'attr_values': attr_errors}
                )

            # ── Step 4：批量保存属性值 ──
            for av_ser in av_serializers:
                av_ser.save()

        return success_response(
            data=serializer.data,
            message='创建成功',
            status_code=status.HTTP_201_CREATED
        )

    @action(methods=['PATCH'], detail=True, url_path='update')
    def update_product(self, request, pk=None):
        """
        修改商品信息（同时更新/新增动态属性值，不允许修改所属品类）
        PATCH /api/products/<id>/update/

        请求体（application/json 或 multipart/form-data）：
          product_name   — 新商品名称（可选）
          product_price  — 新价格（可选）
          product_stock  — 新库存（可选）
          product_image  — 新图片（可选，multipart 时使用）
          attr_values    — 属性值列表（可选）
                           每项包含 attr_def ID 和对应值字段；
                           已有记录的更新，尚无记录的新建

        处理流程：
          1. 校验商品基本信息
          2. 预校验所有属性值（Update/Create 序列化器）
          3. 在同一事务中保存，任一失败全部回滚
        """
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        # ── Step 1：校验商品基本信息 ──
        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(message='修改失败', errors=serializer.errors)

        attr_values_raw = _parse_attr_values(request.data)

        # ── Step 2：预校验属性值（在事务外提前校验，减少事务持有时间）──
        av_serializers, attr_errors = _validate_and_collect_attr_value_serializers(
            product.id, attr_values_raw
        )
        if attr_errors:
            return error_response(
                message='属性值校验失败',
                errors={'attr_values': attr_errors}
            )

        # ── Step 3：事务内保存 ──
        with transaction.atomic():
            serializer.save()
            for av_ser in av_serializers:
                av_ser.save()

        return success_response(data=serializer.data, message='修改成功')

    @action(methods=['DELETE'], detail=True, url_path='delete')
    def delete_product(self, request, pk=None):
        """
        逻辑删除商品（级联逻辑删除该商品的所有属性值）
        DELETE /api/products/<id>/delete/

        级联说明：
          商品删除后，其下所有 ProductAttrValue 也同步标记为已删除，
          避免产生孤悬的属性值记录，保持数据完整性。
          使用事务保证商品与属性值的删除原子性。
        """
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            # 级联逻辑删除所有属性值
            ProductAttrValue.objects.filter(
                product=product,
                is_delete=DeleteStatus.NORMAL
            ).update(is_delete=DeleteStatus.DELETED)

            product.is_delete = DeleteStatus.DELETED
            product.save()

        return success_response(message='删除成功')
