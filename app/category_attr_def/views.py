from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status

from .models import CategoryAttrDef
from .serializers import (
    CategoryAttrDefListSerializer,
    CategoryAttrDefCreateSerializer,
    CategoryAttrDefUpdateSerializer,
)
from app.product_attr_value.models import ProductAttrValue
from app.utils import success_response, error_response
from app.dicts import DeleteStatus


class CategoryAttrDefViewSet(ViewSet):
    """
    品类属性定义模块视图集
    所有品类属性定义相关接口统一在此管理
    """

    def get_attr_def_or_none(self, pk):
        """根据 id 获取未删除的属性定义，不存在则返回 None"""
        try:
            return CategoryAttrDef.objects.get(id=pk, is_delete=DeleteStatus.NORMAL)
        except CategoryAttrDef.DoesNotExist:
            return None

    @action(methods=['GET'], detail=False, url_path='dir')
    def dir_attr_def(self, request):
        """
        查询指定品类下的所有属性定义
        GET /api/attr-defs/dir/?category_id=<id>
        category_id 为必传查询参数
        """
        category_id = request.query_params.get('category_id')
        if not category_id:
            return error_response(message='category_id 不能为空')

        attr_defs = CategoryAttrDef.objects.filter(
            category_id=category_id,
            is_delete=DeleteStatus.NORMAL
        )
        serializer = CategoryAttrDefListSerializer(attr_defs, many=True)
        return success_response(data=serializer.data)

    @action(methods=['POST'], detail=False, url_path='create')
    def create_attr_def(self, request):
        """
        新增属性定义
        POST /api/attr-defs/create/
        """
        serializer = CategoryAttrDefCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message='创建成功', status_code=status.HTTP_201_CREATED)
        return error_response(message='创建失败', errors=serializer.errors)

    @action(methods=['PATCH'], detail=True, url_path='update')
    def update_attr_def(self, request, pk=None):
        """
        修改属性定义（只允许修改属性名称和是否必填）
        PATCH /api/attr-defs/<id>/update/
        """
        attr_def = self.get_attr_def_or_none(pk)
        if not attr_def:
            return error_response(message='属性定义不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        serializer = CategoryAttrDefUpdateSerializer(attr_def, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message='修改成功')
        return error_response(message='修改失败', errors=serializer.errors)

    @action(methods=['DELETE'], detail=True, url_path='delete')
    def delete_attr_def(self, request, pk=None):
        """
        逻辑删除属性定义
        DELETE /api/attr-defs/<id>/delete/
        """
        attr_def = self.get_attr_def_or_none(pk)
        if not attr_def:
            return error_response(message='属性定义不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        # ────────────────────────────────────────────────────
        # 精准删除保护：检查是否有商品已为该属性定义填写了属性值
        #
        # 背景：属性定义是商品属性值（ProductAttrValue）的模板来源。
        #       若直接逻辑删除属性定义，已关联到它的 ProductAttrValue
        #       记录将变成孤悬数据（引用一个已删除的属性定义），破坏
        #       数据完整性。
        #
        # 设计选择：此处采用"精准拦截"而非"品类有商品即拦截"：
        #   - 只要没有商品实际填写过该属性的值，即可安全删除
        #   - 即使品类下有商品，只要该属性从未被填写，也允许删除
        #   - 这比"品类有商品就全部拦截"更灵活，不会因为品类有商品
        #     就完全无法清理废弃属性定义
        #
        # 正确操作顺序：若该属性已有填写记录，需先在商品属性值页面
        #               删除相关记录，再回来删除属性定义。
        # ────────────────────────────────────────────────────
        if ProductAttrValue.objects.filter(attr_def=attr_def, is_delete=DeleteStatus.NORMAL).exists():
            return error_response(
                message='该属性定义已有商品填写了属性值，请先删除相关商品属性值后再操作',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        attr_def.is_delete = DeleteStatus.DELETED
        attr_def.save()
        return success_response(message='删除成功')
