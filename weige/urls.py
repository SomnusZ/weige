from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from app import test_views

urlpatterns = [
    # Django 后台管理
    path('admin/', admin.site.urls),

    # 业务模块接口，统一加 /api/ 前缀
    path('api/', include('app.category.urls')),             # 品类模块
    path('api/', include('app.category_attr_def.urls')),    # 品类属性定义模块
    path('api/', include('app.product.urls')),              # 商品模块
    path('api/', include('app.product_attr_value.urls')),   # 商品属性值模块

    # 测试页面（通用路由）自动映射到 templates/test/<name>.html
    path('test/<str:name>/', test_views.test_page, name='test-page'),
]

# 开发环境下提供媒体文件访问（生产环境由 Nginx 处理）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
