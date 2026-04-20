from rest_framework.routers import DefaultRouter
from . import views

# Router 自动根据 ViewSet 生成路由
router = DefaultRouter()
router.register('categories', views.CategoryViewSet, basename='category')

urlpatterns = router.urls
