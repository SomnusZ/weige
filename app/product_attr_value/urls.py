from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('attr-values', views.ProductAttrValueViewSet, basename='attr-value')

urlpatterns = router.urls
