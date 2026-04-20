from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status

from .models import Product
from .serializers import ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer
from app.utils import success_response, error_response
from app.dicts import DeleteStatus


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

        # 可选：按品类筛选
        category_id = request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        serializer = ProductListSerializer(queryset, many=True)
        return success_response(data=serializer.data)

    @action(methods=['POST'], detail=False, url_path='create')
    def create_product(self, request):
        """
        新增商品
        POST /api/products/create/
        """
        serializer = ProductCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message='创建成功', status_code=status.HTTP_201_CREATED)
        return error_response(message='创建失败', errors=serializer.errors)

    @action(methods=['PATCH'], detail=True, url_path='update')
    def update_product(self, request, pk=None):
        """
        修改商品信息（不允许修改所属品类）
        PATCH /api/products/<id>/update/
        """
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message='修改成功')
        return error_response(message='修改失败', errors=serializer.errors)

    @action(methods=['DELETE'], detail=True, url_path='delete')
    def delete_product(self, request, pk=None):
        """
        逻辑删除商品
        DELETE /api/products/<id>/delete/
        """
        product = self.get_product_or_none(pk)
        if not product:
            return error_response(message='商品不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        product.is_delete = DeleteStatus.DELETED
        product.save()
        return success_response(message='删除成功')
