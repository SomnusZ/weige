from django.apps import AppConfig


class CategoryConfig(AppConfig):
    # 默认主键类型
    default_auto_field = 'django.db.models.BigAutoField'
    # app 完整路径，与 settings.py 中 INSTALLED_APPS 注册名一致
    name = 'app.category'
    # Admin 后台显示名称
    verbose_name = '商品品类'
