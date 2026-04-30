from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import LoginSerializer, UserInfoSerializer, UserCreateSerializer
from app.utils import success_response, error_response


class UserViewSet(ViewSet):
    """
    用户模块视图集
    """

    @action(methods=['POST'], detail=False, url_path='login', permission_classes=[AllowAny])
    def login(self, request):
        """
        管理员登录
        POST /api/users/login/

        请求体（application/json）：
          phone    — 手机号
          password — 密码

        响应：
          access   — 短期 token，携带在请求头 Authorization: Bearer <access>
          refresh  — 长期 token，用于换取新 access token
          user     — 当前用户基本信息
        """
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return error_response(message='登录失败', errors=serializer.errors)

        user          = serializer.validated_data['user']
        refresh       = RefreshToken.for_user(user)
        user_info     = UserInfoSerializer(user).data

        return success_response(
            message='登录成功',
            data={
                'access' : str(refresh.access_token),
                'refresh': str(refresh),
                'user'   : user_info,
            }
        )

    @action(methods=['POST'], detail=False, url_path='token/refresh', permission_classes=[AllowAny])
    def token_refresh(self, request):
        """
        刷新 access token
        POST /api/users/token/refresh/

        请求体：
          refresh — refresh token 字符串

        响应：
          access  — 新的 access token
        """
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return error_response(message='refresh token 不能为空')

        try:
            refresh = RefreshToken(refresh_token)
            return success_response(data={'access': str(refresh.access_token)})
        except Exception:
            return error_response(
                message='refresh token 无效或已过期，请重新登录',
                status_code=status.HTTP_401_UNAUTHORIZED
            )

    @action(
        methods=['GET'],
        detail=False,
        url_path='me',
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        """
        获取当前登录用户信息
        GET /api/users/me/
        需要在请求头携带：Authorization: Bearer <access token>
        """
        serializer = UserInfoSerializer(request.user)
        return success_response(data=serializer.data)

    @action(
        methods=['POST'],
        detail=False,
        url_path='create',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def create_user(self, request):
        """
        新增管理员账号（仅超级管理员可操作）
        POST /api/users/create/

        请求体（application/json）：
          phone        — 手机号（必填）
          password     — 密码（必填，至少6位）
          nickname     — 昵称（可选）
          is_staff     — 是否可访问 Admin 后台（可选，默认 False）
          is_superuser — 是否超级管理员（可选，默认 False）
        """
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response(
                data=UserInfoSerializer(serializer.instance).data,
                message='创建成功',
                status_code=status.HTTP_201_CREATED,
            )
        return error_response(message='创建失败', errors=serializer.errors)
