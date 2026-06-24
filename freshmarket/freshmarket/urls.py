from django.contrib import admin
from django.urls import path, include, re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),  # 富文本编辑器
    re_path(r'^cart/', include(('cart.urls', 'cart'), namespace='cart')),
    re_path(r'^user/', include(('user.urls', 'user'), namespace='user')),
    re_path(r'^order/', include(('order.urls', 'order'), namespace='order')),
    re_path(r'^search', include('haystack.urls')),  # 全文检索框架
    re_path(r'^', include(('goods.urls', 'goods'), namespace='goods')),

]

# 开发环境下由 Django 提供媒体文件(上传的图片)访问
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
