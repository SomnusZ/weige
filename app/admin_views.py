"""
管理后台页面视图 + 登录 API（JWT 版本）
"""
from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from app.utils import success_response, error_response


def login_page(request):
    return render(request, 'login.html')


def dashboard_page(request):
    return render(request, 'dashboard.html')




@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    # login.html 用 username 字段名（标签显示为"用户名"，实际填手机号）
    phone    = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()

    if not phone or not password:
        return error_response('手机号和密码不能为空')

    # USERNAME_FIELD = 'phone'，所以用 phone= 传参
    user = authenticate(request, phone=phone, password=password)
    if not user:
        return error_response('手机号或密码错误')

    if not user.is_active:
        return error_response('账户已被禁用，请联系管理员')

    refresh = RefreshToken.for_user(user)
    return success_response({
        'access' : str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id'          : user.id,
            'phone'       : user.phone,
            'nickname'    : user.nickname or user.phone,
            'is_superuser': user.is_superuser,
        },
    }, message='登录成功')
