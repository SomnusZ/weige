from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework import status

from .models import ProductAttrValue
from .serializers import (
    ProductAttrValueListSerializer,
    ProductAttrValueCreateSerializer,
    ProductAttrValueUpdateSerializer,
)
from app.utils import success_response, error_response
from app.dicts import DeleteStatus


class ProductAttrValueViewSet(ViewSet):
    """
    商品属性值模块视图集（EAV 核心模块）
    所有商品属性值相关接口统一在此管理
    """

    def get_attr_value_or_none(self, pk):
        """根据 id 获取未删除的属性值记录，不存在则返回 None"""
        try:
            return ProductAttrValue.objects.get(id=pk, is_delete=DeleteStatus.NORMAL)
        except ProductAttrValue.DoesNotExist:
            return None

    @action(methods=['GET'], detail=False, url_path='dir')
    def dir_attr_value(self, request):
        """
        查询指定商品的所有属性值
        GET /api/attr-values/dir/?product_id=<id>
        product_id 为必传查询参数
        """
        product_id = request.query_params.get('product_id')
        if not product_id:
            return error_response(message='product_id 不能为空')

        attr_values = ProductAttrValue.objects.filter(
            product_id=product_id,
            is_delete=DeleteStatus.NORMAL
        )
        serializer = ProductAttrValueListSerializer(attr_values, many=True)
        return success_response(data=serializer.data)

    @action(methods=['POST'], detail=False, url_path='create')
    def create_attr_value(self, request):
        """
        新增商品属性值
        POST /api/attr-values/create/
        """
        serializer = ProductAttrValueCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message='创建成功', status_code=status.HTTP_201_CREATED)
        return error_response(message='创建失败', errors=serializer.errors)

    @action(methods=['PATCH'], detail=True, url_path='update')
    def update_attr_value(self, request, pk=None):
        """
        修改商品属性值（只允许修改值字段，不允许修改商品或属性定义）
        PATCH /api/attr-values/<id>/update/
        """
        attr_value = self.get_attr_value_or_none(pk)
        if not attr_value:
            return error_response(message='属性值不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        serializer = ProductAttrValueUpdateSerializer(attr_value, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message='修改成功')
        return error_response(message='修改失败', errors=serializer.errors)

    # ════════════════════════════════════════════════════════════
    # [DEPRECATED] delete_attr_value — 商品属性值逻辑删除接口（已弃用）
    #
    # 弃用原因：
    #   update_attr_value（PATCH）已可覆盖属性值的所有修改场景；
    #   单独的删除入口容易造成数据不完整（商品缺少必填属性值），
    #   故弃用此接口，统一通过 update 操作维护属性值。
    #
    # 改动说明（2026-04-22）：
    #   • HTTP 方法保持 DELETE 不变，不影响已有调用方。
    #   • 业务逻辑代码完整保留，接口仍可正常响应，
    #     仅通过注释声明弃用状态，提示后续开发者不要再扩展此入口。
    # ════════════════════════════════════════════════════════════
    @action(methods=['DELETE'], detail=True, url_path='delete')
    def delete_attr_value(self, request, pk=None):
        """
        [DEPRECATED] 逻辑删除商品属性值 — 此接口已弃用，请改用 update_attr_value
        DELETE /api/attr-values/<id>/delete/
        """
        attr_value = self.get_attr_value_or_none(pk)
        if not attr_value:
            return error_response(message='属性值不存在或已被删除', status_code=status.HTTP_404_NOT_FOUND)

        attr_value.is_delete = DeleteStatus.DELETED
        attr_value.save()
        return success_response(message='删除成功')
