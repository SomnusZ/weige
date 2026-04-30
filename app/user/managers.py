from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    自定义用户管理器
    以手机号作为登录凭证（替代默认的 username）
    """

    def create_user(self, phone, password=None, **extra_fields):
        """
        创建普通用户
        is_staff / is_superuser 默认为 False
        """
        if not phone:
            raise ValueError('手机号不能为空')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra_fields):
        """
        创建超级管理员（用于 python manage.py createsuperuser）
        强制 is_staff=True、is_superuser=True
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('超级管理员必须设置 is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('超级管理员必须设置 is_superuser=True')

        return self.create_user(phone, password, **extra_fields)
