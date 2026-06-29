from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include, re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin_panel/', include(('admin.urls', 'admin_panel'), namespace='admin_panel')),
    path('tinymce/', include('tinymce.urls')),  # 富文本编辑器
    re_path(r'^search/', include('haystack.urls')),  # 全文检索框架

    # ===== 用户端密码重置（user/ 模块负责）=====
    path('user/password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='user/password_reset_form.html',
             email_template_name='user/password_reset_email.html',
             subject_template_name='user/password_reset_subject.txt',
             success_url='/user/password_reset/done/',
         ),
         name='password_reset'),
    path('user/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='user/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('user/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='user/password_reset_confirm.html',
             success_url='/user/reset/done/',
         ),
         name='password_reset_confirm'),
    path('user/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='user/password_reset_complete.html',
         ),
         name='password_reset_complete'),

    re_path(r'^cart/', include(('cart.urls', 'cart'), namespace='cart')),
    re_path(r'^user/', include(('user.urls', 'user'), namespace='user')),
    re_path(r'^order/', include(('order.urls', 'order'), namespace='order')),
    re_path(r'^', include(('goods.urls', 'goods'), namespace='goods')),
]

# 开发环境下由 Django 提供媒体文件(上传的图片)访问
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
