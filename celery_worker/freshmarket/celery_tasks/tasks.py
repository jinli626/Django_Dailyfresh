# 现在开始编写异步处理代码
from email.utils import formataddr

import django
# 注册
from django.core.mail import send_mail
from django.conf import settings
import time

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freshmarket.settings')
django.setup()

import os
from celery import Celery

app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/0')


@app.task
def send_register_active_email(to_email, username, token):
    """处理逻辑不变，直接复制即可"""
    # 发送邮件
    # 设置发件人显示为：天天生鲜 <2197381455@qq.com>
    from_email = formataddr(("天天生鲜", settings.EMAIL_HOST_USER))

    subject = '欢迎注册天天生鲜'
    message = f"""
           感谢您注册天天生鲜！

           请点击下面的链接激活您的账户：
           http://127.0.0.1:8000/user/active/{token}

           如果这不是您本人的操作，请忽略此邮件。
           """.strip()

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[to_email]
    )
