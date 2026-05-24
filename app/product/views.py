import json

from django.db import transaction
from django.db.models import Prefetch, Max
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import Product, ProductImage
from .serializers import (
    ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer,
    ProductPublicSerializer, ProductImageSerializer,
)
from app.category.models import Category
from app.product_attr_value.models import ProductAttrValue
from app.product_attr_value.serializers import (
    ProductAttrValueCreateSerializer,
    ProductAttrValueUpdateSerializer,
)
from app.category_attr_def.models import CategoryAttrDef
from app.utils import success_response, error_response
from app.dicts import DeleteStatus, ATTR_TYPE_FIELD_MAP

MAX_IMAGES = 9


def get_category_ids_with_descendants(category_id):
    ids = [category_id]
    children = Category.objects.filter(
        parent_id=category_id,
        is_delete=DeleteStatus.NORMAL
    ).values_list('id', flat=True)
    for child_id in children:
        ids.extend(get_category_ids_with_descendants(child_id))
    return ids


def _parse_attr_values(request_data):
    raw = request_data.get('attr_values', [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raw = []
    return raw if isinstance(raw, list) else []


def _validate_and_collect_attr_value_serializers(product_id, attr_values_raw):
    av_serializers = []
    errors = {}

    for i, av_data in enumerate(attr_values_raw):
        attr_def_id = av_data.get('attr_def')

        existing = ProductAttrValue.objects.filter(
            product_id=product_id,
            attr_def_id=attr_def_id,
            is_delete=DeleteStatus.NORMAL
        ).first()

        if existing:
            av_ser = ProductAttrValueUpdateSerializer(existing, data=av_data, partial=True)
        else:
            data = {**av_data, 'product': product_id}
            av_ser = ProductAttrValueCreateSerializer(data=data)

        if av_ser.is_valid():
            av_serializers.append(av_ser)
        else:
            errors[i] = av_ser.errors

    return av_serializers, errors


def _img_prefetch_qs():
    return ProductImage.objects.filter(is_delete=DeleteStatus.NORMAL).order_by('sort_order', 'id')


class ProductViewSet(ViewSet):

    def get_product_or_none(self, pk):
        try:
            return Product.objects.get(id=pk, is_delete=DeleteStatus.NORMAL)
        except Product.DoesNotExist:
            return None

    # ── 前台公开列表 ──────────────────────────────────────────────────────────

    @action(methods=['GET'], detail=False, url_path='public', permission_classes=[AllowAny])
    def public_list(self, request):
        av_qs = ProductAttrValue.objects.filter(
            is_delete=DeleteStatus.NORMAL
        ).select_related('attr_def').order_by('id')

        queryset = (
            Product.objects
            .filter(is_delete=DeleteStatus.NORMAL)
            .select_related('category')
            .prefetch_related(
                Prefetch('images', queryset=_img_prefetch_qs(), to_attr='prefetched_images'),
                Prefetch('attr_values', queryset=av_qs, to_attr='prefetched_attr_values'),
            )
        )

        category_id = request.query_params.get('category_id')
        if category_id:
            try:
                cat_ids = get_category_ids_with_descendants(int(category_id))
                queryset = queryset.filter(category_id__in=cat_ids)
            except (ValueError, TypeError):
                pass

        keyword = request.query_params.get('q', '').strip()
        if keyword:
            queryset = queryset.filter(product_name__icontains=keyword)

        attr_filters = {}
        for key in request.query_params:
            if key.startswith('attr_'):
                try:
                    attr_def_id = int(key[5:])
                except ValueError:
                    continue
                values = request.query_params.getlist(key)
                if values:
                    attr_filters[attr_def_id] = values

        for attr_def_id, values in attr_filters.items():
            try:
                attr_def = CategoryAttrDef.objects.get(id=attr_def_id, is_delete=DeleteStatus.NORMAL)
            except CategoryAttrDef.DoesNotExist:
                continue

            field_name = ATTR_TYPE_FIELD_MAP.get(attr_def.value_type)
            if not field_name:
                continue

            if attr_def.value_type == 'bool':
                bool_values = []
                for v in values:
                    if v == '是':
                        bool_values.append(True)
                    elif v == '否':
                        bool_values.append(False)
                if not bool_values:
                    continue
                filter_values = bool_values
            elif attr_def.value_type == 'int':
                try:
                    filter_values = [int(v) for v in values]
                except ValueError:
                    continue
            elif attr_def.value_type == 'float':
                try:
                    filter_values = [float(v) for v in values]
                except ValueError:
                    continue
            else:
                filter_values = values

            queryset = queryset.filter(
                attr_values__attr_def_id=attr_def_id,
                attr_values__is_delete=DeleteStatus.NORMAL,
                **{f'attr_values__{field_name}__in': filter_values}
            )

        serializer = ProductPublicSerializer(queryset, many=True, context={'request': request})
        return success_response(data=serializer.data)

    # ── 筛选选项 ─────────────────────────────────────────────────────────────

    @action(methods=['GET'], detail=False, url_path='filter-options', permission_classes=[AllowAny])
    def filter_options(self, request):
        category_id = request.query_params.get('category_id')
        if not category_id:
            return success_response(data=[])

        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            return success_response(data=[])

        attr_defs = CategoryAttrDef.objects.filter(
            category_id=category_id,
            is_delete=DeleteStatus.NORMAL
        ).order_by('id')

        result = []
        for attr_def in attr_defs:
            field_name = ATTR_TYPE_FIELD_MAP.get(attr_def.value_type)
            if not field_name:
                continue

            qs = (
                ProductAttrValue.objects
                .filter(
                    attr_def=attr_def,
                    is_delete=DeleteStatus.NORMAL,
                    product__is_delete=DeleteStatus.NORMAL,
                    **{f'{field_name}__isnull': False}
                )
                .values_list(field_name, flat=True)
                .distinct()
                .order_by(field_name)
            )

            if attr_def.value_type == 'bool':
                raw_values = list(qs)
                values = []
                if True in raw_values:
                    values.append('是')
                if False in raw_values:
                    values.append('否')
            else:
                values = [str(v) for v in qs]

            if not values:
                continue

            result.append({
                'attr_def_id': attr_def.id,
                'attr_name':   attr_def.attr_name,
                'value_type':  attr_def.value_type,
                'values':      values,
            })

        return success_response(data=result)

    # ── 后台列表 ──────────────────────────────────────────────────────────────

    @action(methods=['GET'], detail=False, url_path='dir')
    def dir_product(self, request):
        queryset = (
            Product.objects
            .filter(is_delete=DeleteStatus.NORMAL)
            .prefetch_related(Prefetch('images', queryset=_img_prefetch_qs(), to_attr='prefetched_images'))
        )

        category_id = request.query_params.get('category_id')
        if category_id:
            category_ids = get_category_ids_with_descendants(int(category_id))
            queryset = queryset.filter(category_id__in=category_ids)

        serializer = ProductListSerializer(queryset, many=True, context={'request': request})
        return success_response(data=serializer.data)

    # ── 新增商品 ──────────────────────────────────────────────────────────────

    @action(methods=['POST'], detail=False, url_path='create')
    def create_product(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message='创建失败', errors=serializer.errors)

        files = request.FILES.getlist('product_images')
        if len(files) > MAX_IMAGES:
            return error_response(message=f'最多上传 {MAX_IMAGES} 张图片')

        attr_values_raw = _parse_attr_values(request.data)

        with transaction.atomic():
            product = serializer.save()

            for i, f in enumerate(files):
                ProductImage.objects.create(
                    product=product,
                    image=f,
                    is_primary=(i == 0),
                    sort_order=i,
                )

            av_serializers, attr_errors = _validate_and_collect_attr_value_serializers(
                product.id, attr_values_raw
            )
            if attr_errors:
                transaction.set_rollback(True)
                return error_response(message='属性值校验失败', errors={'attr_values': attr_errors})

            for av_ser in av_serializers:
                av_ser.save()

        return success_response(
            data=serializer.data,
            message='创建成功',
            status_code=status.HTTP_201_CREATED
        )

    # ── 修改商品（基本信息 + 属性值，图片单独管理）────────────────────────────

    @action(methods=['PATCH'], detail=True, url_path='update')
    def update_product(self, request, pk=None):
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(message='修改失败', errors=serializer.errors)

        attr_values_raw = _parse_attr_values(request.data)
        av_serializers, attr_errors = _validate_and_collect_attr_value_serializers(
            product.id, attr_values_raw
        )
        if attr_errors:
            return error_response(message='属性值校验失败', errors={'attr_values': attr_errors})

        with transaction.atomic():
            serializer.save()
            for av_ser in av_serializers:
                av_ser.save()

        return success_response(data=serializer.data, message='修改成功')

    # ── 删除商品 ──────────────────────────────────────────────────────────────

    @action(methods=['DELETE'], detail=True, url_path='delete')
    def delete_product(self, request, pk=None):
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            ProductAttrValue.objects.filter(
                product=product,
                is_delete=DeleteStatus.NORMAL
            ).update(is_delete=DeleteStatus.DELETED)
            ProductImage.objects.filter(
                product=product,
                is_delete=DeleteStatus.NORMAL
            ).update(is_delete=DeleteStatus.DELETED)
            product.is_delete = DeleteStatus.DELETED
            product.save()

        return success_response(message='删除成功')

    # ── 图片列表 ──────────────────────────────────────────────────────────────

    @action(methods=['GET'], detail=True, url_path='images')
    def list_images(self, request, pk=None):
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        images = ProductImage.objects.filter(
            product=product, is_delete=DeleteStatus.NORMAL
        ).order_by('sort_order', 'id')
        serializer = ProductImageSerializer(images, many=True, context={'request': request})
        return success_response(data=serializer.data)

    # ── 新增图片 ──────────────────────────────────────────────────────────────

    @action(methods=['POST'], detail=True, url_path='images/add')
    def add_images(self, request, pk=None):
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        files = request.FILES.getlist('images')
        if not files:
            return error_response(message='请选择图片')

        existing_count = ProductImage.objects.filter(
            product=product, is_delete=DeleteStatus.NORMAL
        ).count()
        if existing_count + len(files) > MAX_IMAGES:
            remain = MAX_IMAGES - existing_count
            return error_response(message=f'最多 {MAX_IMAGES} 张图片，当前已有 {existing_count} 张，还可添加 {remain} 张')

        has_primary = ProductImage.objects.filter(
            product=product, is_delete=DeleteStatus.NORMAL, is_primary=True
        ).exists()
        max_order = ProductImage.objects.filter(
            product=product, is_delete=DeleteStatus.NORMAL
        ).aggregate(Max('sort_order'))['sort_order__max']
        next_order = (max_order + 1) if max_order is not None else 0

        created = []
        for i, f in enumerate(files):
            is_primary = (not has_primary and i == 0)
            img = ProductImage.objects.create(
                product=product,
                image=f,
                is_primary=is_primary,
                sort_order=next_order + i,
            )
            if is_primary:
                has_primary = True
            created.append(img)

        serializer = ProductImageSerializer(created, many=True, context={'request': request})
        return success_response(data=serializer.data, message='上传成功')

    # ── 删除单张图片 ──────────────────────────────────────────────────────────

    @action(methods=['DELETE'], detail=False, url_path=r'images/(?P<img_id>\d+)/delete')
    def delete_image(self, request, img_id=None):
        try:
            img = ProductImage.objects.get(id=img_id, is_delete=DeleteStatus.NORMAL)
        except ProductImage.DoesNotExist:
            return error_response(message='图片不存在', status_code=status.HTTP_404_NOT_FOUND)

        was_primary = img.is_primary
        img.is_delete = DeleteStatus.DELETED
        img.save()

        if was_primary:
            next_img = ProductImage.objects.filter(
                product=img.product, is_delete=DeleteStatus.NORMAL
            ).order_by('sort_order', 'id').first()
            if next_img:
                next_img.is_primary = True
                next_img.save()

        return success_response(message='删除成功')

    # ── 设置主图 ──────────────────────────────────────────────────────────────

    @action(methods=['PATCH'], detail=False, url_path=r'images/(?P<img_id>\d+)/set-primary')
    def set_primary_image(self, request, img_id=None):
        try:
            img = ProductImage.objects.get(id=img_id, is_delete=DeleteStatus.NORMAL)
        except ProductImage.DoesNotExist:
            return error_response(message='图片不存在', status_code=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            ProductImage.objects.filter(
                product=img.product, is_delete=DeleteStatus.NORMAL
            ).update(is_primary=False)
            img.is_primary = True
            img.save()

        return success_response(message='主图已更新')

    # ── 拖拽排序 ──────────────────────────────────────────────────────────────

    @action(methods=['PATCH'], detail=True, url_path='images/reorder')
    def reorder_images(self, request, pk=None):
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        order_data = request.data.get('order', [])
        if not order_data:
            return error_response(message='缺少排序数据')

        with transaction.atomic():
            for item in order_data:
                img_id = item.get('id')
                sort_order = item.get('sort_order')
                if img_id is None or sort_order is None:
                    continue
                ProductImage.objects.filter(
                    id=img_id, product=product, is_delete=DeleteStatus.NORMAL
                ).update(sort_order=sort_order)

        return success_response(message='排序已更新')
