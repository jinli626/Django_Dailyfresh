import re

from django.conf import settings
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from user.models import User

EMAIL_RE = r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$'


class AdminRegisterView(View):
    """管理员注册"""

    def get(self, request):
        return render(request, 'admin/register.html', {
            'invite_code': settings.ADMIN_INVITE_CODE,
        })

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.POST.get('email')
        invite_code = request.POST.get('invite_code', '')

        if not all([username, password, confirm_password, email]):
            return render(request, 'admin/register.html', {
                'errmsg': '数据不完整',
                'invite_code': settings.ADMIN_INVITE_CODE,
            })
        if not re.match(EMAIL_RE, email):
            return render(request, 'admin/register.html', {
                'errmsg': '邮箱格式不正确！',
                'invite_code': settings.ADMIN_INVITE_CODE,
            })
        if password != confirm_password:
            return render(request, 'admin/register.html', {
                'errmsg': '两次输入的密码不一致',
                'invite_code': settings.ADMIN_INVITE_CODE,
            })
        if len(password) < 6:
            return render(request, 'admin/register.html', {
                'errmsg': '密码长度不能少于6位',
                'invite_code': settings.ADMIN_INVITE_CODE,
            })
        if User.objects.filter(username=username).exists():
            return render(request, 'admin/register.html', {
                'errmsg': '用户名已存在',
                'invite_code': settings.ADMIN_INVITE_CODE,
            })
        if invite_code != settings.ADMIN_INVITE_CODE:
            return render(request, 'admin/register.html', {
                'errmsg': '邀请码错误，请联系管理员获取',
                'invite_code': settings.ADMIN_INVITE_CODE,
            })

        user = User.objects.create_user(username, email, password)
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save()

        login(request, user)
        return redirect('/admin/')


def admin_logout_view(request):
    """管理员退出登录"""
    logout(request)
    return redirect('/admin/login/')
