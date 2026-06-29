"""
重置管理员密码命令
用法: python manage.py reset_admin [用户名] [新密码]
默认: python manage.py reset_admin admin admin123
"""
from django.core.management.base import BaseCommand
from user.models import User


class Command(BaseCommand):
    help = '重置管理员密码，并将其设为超级管理员'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', help='管理员用户名 (默认: admin)')
        parser.add_argument('--password', default='admin123', help='新密码 (默认: admin123)')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']

        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'已创建管理员: {username}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'管理员密码已重置: {username}'))

        self.stdout.write(f'  用户名: {username}')
        self.stdout.write(f'  密码:   {password}')
