from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('attr-defs', views.CategoryAttrDefViewSet, basename='attr-def')

urlpatterns = router.urls
