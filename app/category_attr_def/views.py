from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status

from .models import CategoryAttrDef
from .serializers import (
    CategoryAttrDefListSerializer,
    CategoryAttrDefCreateSerializer,
    CategoryAttrDefUpdateSerializer,
)
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

        attr_def.is_delete = DeleteStatus.DELETED
        attr_def.save()
        return success_response(message='删除成功')
