from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User


class LoginSerializer(serializers.Serializer):
    """
    登录序列化器
    校验手机号和密码，返回 User 对象供 View 层生成 token
    """
    phone    = serializers.CharField(label='手机号')
    password = serializers.CharField(label='密码', write_only=True)

    def validate(self, attrs):
        phone    = attrs.get('phone')
        password = attrs.get('password')

        # authenticate 内部调用 check_password，手机号对应 USERNAME_FIELD
        user = authenticate(
            request=self.context.get('request'),
            phone=phone,
            password=password,
        )

        if not user:
            raise serializers.ValidationError('手机号或密码错误')
        if not user.is_active:
            raise serializers.ValidationError('账号已被禁用，请联系管理员')

        attrs['user'] = user
        return attrs


class UserInfoSerializer(serializers.ModelSerializer):
    """
    用户信息序列化器（用于 GET /api/users/me/）
    只返回前端需要的安全字段，不暴露密码哈希
    """

    class Meta:
        model  = User
        fields = ['id', 'phone', 'nickname', 'is_staff', 'is_superuser', 'create_time']


class UserCreateSerializer(serializers.ModelSerializer):
    """
    创建用户序列化器（用于后台新增管理员账号）
    password 接收明文，save() 时自动哈希
    """
    password = serializers.CharField(write_only=True, min_length=6, label='密码')

    class Meta:
        model  = User
        fields = ['phone', 'password', 'nickname', 'is_staff', 'is_superuser']

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('该手机号已注册')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)   # 哈希后存储
        user.save()
        return user
