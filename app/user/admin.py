from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    用户 Admin 配置
    继承 BaseUserAdmin 以复用密码修改表单等内置功能
    """
    list_display  = ('phone', 'nickname', 'is_active', 'is_staff', 'is_superuser', 'create_time')
    list_filter   = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('phone', 'nickname')
    ordering      = ('-create_time',)

    # 查看/编辑用户时显示的字段分组
    fieldsets = (
        ('账号信息', {'fields': ('phone', 'password')}),
        ('基本信息', {'fields': ('nickname',)}),
        ('权限',    {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    # 新增用户时显示的字段（Admin 后台内新增）
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields' : ('phone', 'nickname', 'password1', 'password2',
                        'is_staff', 'is_superuser'),
        }),
    )

    # 覆盖父类默认字段（父类用 username，我们用 phone）
    filter_horizontal = ('groups', 'user_permissions')
