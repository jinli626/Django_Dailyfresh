from django.contrib.auth import views as auth_views
from django.urls import path

from admin.views import AdminRegisterView, admin_logout_view

app_name = 'admin_panel'

urlpatterns = [
    # 管理员退出登录
    path('logout/', admin_logout_view, name='logout'),

    # 管理员注册
    path('register/', AdminRegisterView.as_view(), name='register'),

    # 管理端密码重置（管理员界面，独立于用户端）
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='admin/password_reset_form.html',
             email_template_name='admin/password_reset_email.html',
             subject_template_name='user/password_reset_subject.txt',
             success_url='/admin_panel/password_reset/done/',
         ),
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='admin/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='admin/password_reset_confirm.html',
             success_url='/admin_panel/reset/done/',
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='admin/password_reset_complete.html',
         ),
         name='password_reset_complete'),
]
