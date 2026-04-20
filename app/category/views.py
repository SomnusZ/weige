from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status

from .models import Category
from .serializers import CategoryListSerializer, CategoryWriteSerializer
from app.utils import success_response, error_response
from app.dicts import DeleteStatus


class CategoryViewSet(ViewSet):
    """
    品类模块视图集
    所有品类相关接口统一在此管理
    """

    def get_category_or_none(self, pk):
        """根据 id 获取未删除的品类，不存在则返回 None"""
        try:
            return Category.objects.get(id=pk, is_delete=DeleteStatus.NORMAL)
        except Category.DoesNotExist:
            return None

    @action(methods=['GET'], detail=False, url_path='dir')
    def dir_category(self, request):
        """
        查询所有品类（平铺列表，前端负责组装树结构）
        GET /api/categories/dir/
        """
        categories = Category.objects.filter(is_delete=DeleteStatus.NORMAL)
        serializer = CategoryListSerializer(categories, many=True)
        return success_response(data=serializer.data)

    @action(methods=['POST'], detail=False, url_path='create')
    def create_category(self, request):
        """
        新增品类
        POST /api/categories/create/
        """
        serializer = CategoryWriteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message="创建成功", status_code=status.HTTP_201_CREATED)
        return error_response(message="创建失败", errors=serializer.errors)

    @action(methods=['PATCH'], detail=True, url_path='update')
    def update_category(self, request, pk=None):
        """
        修改品类（只允许修改名称和父级关系）
        PATCH /api/categories/<id>/update/
        """
        category = self.get_category_or_none(pk)
        if not category:
            return error_response(message="品类不存在或已被删除", status_code=status.HTTP_404_NOT_FOUND)

        # partial=True 表示允许只传部分字段（局部更新）
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message="修改成功")
        return error_response(message="修改失败", errors=serializer.errors)

    @action(methods=['DELETE'], detail=True, url_path='delete')
    def delete_category(self, request, pk=None):
        """
        逻辑删除品类（is_delete 置为 True，不真正删除数据）
        DELETE /api/categories/<id>/delete/
        """
        category = self.get_category_or_none(pk)
        if not category:
            return error_response(message="品类不存在或已被删除", status_code=status.HTTP_404_NOT_FOUND)

        category.is_delete = DeleteStatus.DELETED
        category.save()
        return success_response(message="删除成功")
