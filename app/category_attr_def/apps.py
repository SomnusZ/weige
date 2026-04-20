from django.apps import AppConfig


class CategoryAttrDefConfig(AppConfig):
    # 默认主键类型
    default_auto_field = 'django.db.models.BigAutoField'
    # app 完整路径，与 settings.py 中 INSTALLED_APPS 注册名一致
    name = 'app.category_attr_def'
    # Admin 后台显示名称
    verbose_name = '品类属性定义'
