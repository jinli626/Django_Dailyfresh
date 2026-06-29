from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from admin.views import AdminRegisterView, admin_logout_view

app_name = 'admin_panel'

# 统一抽取模板，消除重复
TPL = {
    "reset_form": "admin/password_reset_form.html",
    "reset_done": "admin/password_reset_done.html",
    "reset_confirm": "admin/password_reset_confirm.html",
    "reset_complete": "admin/password_reset_complete.html",
}

urlpatterns = [
    path('logout/', admin_logout_view, name='logout'),
    path('register/', AdminRegisterView.as_view(), name='register'),

    # 1. 提交邮箱发重置邮件
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name=TPL["reset_form"],
            email_template_name="admin/password_reset_email.html",
            subject_template_name="user/password_reset_subject.txt",
            success_url=reverse_lazy(f"{app_name}:password_reset_done"),
        ),
        name="password_reset",
    ),
    # 2. 邮件发送成功页
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name=TPL["reset_done"]),
        name="password_reset_done",
    ),
    # 3. 打开链接重置新密码
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name=TPL["reset_confirm"],
            success_url=reverse_lazy(f"{app_name}:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    # 4. 重置全部完成
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name=TPL["reset_complete"]),
        name="password_reset_complete",
    ),
]
