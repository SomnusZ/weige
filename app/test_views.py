"""
测试页面视图
通过通用路由 test/<name>/ 自动映射到 templates/test/<name>.html
新增测试页面只需在 templates/test/ 目录下创建对应 HTML 文件即可，无需修改此文件
"""
from django.shortcuts import render
from django.http import Http404


def test_page(request, name):
    """
    通用测试页面视图
    根据 name 参数自动渲染对应模板
    例：/test/category/  →  templates/test/category.html
    """
    try:
        return render(request, f'test/{name}.html')
    except Exception:
        raise Http404(f'测试页面 [{name}] 不存在')
