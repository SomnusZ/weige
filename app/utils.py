"""
app 公共工具函数
统一封装接口响应格式，便于前端统一处理
"""
from rest_framework.response import Response
from rest_framework import status


def success_response(data=None, message="操作成功", status_code=status.HTTP_200_OK):
    """
    统一成功响应格式
    :param data:        返回的业务数据，默认 None
    :param message:     提示信息，默认"操作成功"
    :param status_code: HTTP 状态码，默认 200
    """
    return Response({
        "success": True,
        "message": message,
        "data": data,
    }, status=status_code)


def error_response(message="操作失败", status_code=status.HTTP_400_BAD_REQUEST, errors=None):
    """
    统一失败响应格式
    :param message:     提示信息，默认"操作失败"
    :param status_code: HTTP 状态码，默认 400
    :param errors:      校验错误详情，默认 None
    """
    return Response({
        "success": False,
        "message": message,
        "data": errors,
    }, status=status_code)
