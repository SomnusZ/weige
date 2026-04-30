from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    自定义用户模型

    使用手机号作为登录凭证，替代 Django 默认的 username。
    继承 AbstractBaseUser 获得密码哈希能力；
    继承 PermissionsMixin 获得 Django Admin 权限体系（groups / permissions）。

    字段说明：
      phone       — 手机号，唯一，作为登录账号
      nickname    — 昵称，可选，用于前端展示
      is_active   — 是否启用（False 表示封号，无法登录）
      is_staff    — 是否可访问 Django Admin 后台
      is_superuser— 超级管理员，拥有所有权限（由 PermissionsMixin 提供）
      create_time — 账号创建时间
    """

    phone = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='手机号',
    )
    nickname = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='昵称',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用',
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='可访问Admin后台',
    )
    create_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间',
    )

    # 指定登录字段（替代 username）
    USERNAME_FIELD = 'phone'
    # createsuperuser 命令除 phone/password 外还会额外询问的字段
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        app_label = 'user'
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return self.nickname or self.phone
