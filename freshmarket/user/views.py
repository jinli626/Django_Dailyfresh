import re

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.sessions.backends.cache import SessionStore
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import View
from django_redis import get_redis_connection
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer as Serializer

from celery_tasks.tasks import send_register_active_email
from goods.models import GoodsSKU
from django.db.models import Case, When, IntegerField

from order.models import OrderGoods, OrderInfo
from user.models import Address, User
from utils.common import paginate

EMAIL_RE = r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$'
PHONE_RE = r'^1[3-9]\d{9}$'
REMEMBER_MAX_AGE = 7 * 24 * 3600


def render_register(request, errmsg):
    return render(request, 'user/register.html', {'errmsg': errmsg})


def make_active_token(user):
    serializer = Serializer(settings.SECRET_KEY)
    return serializer.dumps({'confirm': user.id})


def read_active_token(token):
    serializer = Serializer(settings.SECRET_KEY)
    return serializer.loads(token, max_age=3600)


class RegisterView(View):
    """注册"""

    def get(self, request):
        return render(request, 'user/register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        confirm_password = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        if not all([username, password, email, allow]):
            return render_register(request, '数据不完整')
        if not re.match(EMAIL_RE, email):
            return render_register(request, '邮箱格式不正确！')
        if allow != 'on':
            return render_register(request, '请勾选协议')
        if password != confirm_password:
            return render_register(request, '两次输入的密码不一致')
        if User.objects.filter(username=username).exists():
            return render_register(request, '用户名已存在')

        user = User.objects.create_user(username, email, password)
        user.is_active = False
        user.save()

        token = make_active_token(user)
        send_register_active_email.delay(to_email=email, username=username, token=token)
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """邮箱激活"""

    def get(self, request, token):
        try:
            info = read_active_token(token)
            user = User.objects.get(id=info['confirm'])
        except SignatureExpired:
            return HttpResponse('激活链接已经失效！')
        except (BadSignature, User.DoesNotExist, KeyError):
            return HttpResponse('激活链接无效！')

        user.is_active = True
        user.save()
        return redirect(reverse('user:login'))


class LoginView(View):
    """登录"""

    def get(self, request):
        username = request.COOKIES.get('username', '')
        checked = 'checked' if username else ''
        return render(request, 'user/login.html', {'username': username, 'checked': checked})

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        if not all([username, password]):
            return render(request, 'user/login.html', {
                'errmsg': '账号或者密码不能为空',
                'username': username or '',
            })

        user = authenticate(username=username, password=password)
        if user is None:
            return self.login_failed(request, username, password)

        login(request, user)
        response = redirect(request.GET.get('next', reverse('goods:index')))
        remember = request.POST.get('remember')

        if remember == 'on':
            response.set_cookie('username', username, max_age=REMEMBER_MAX_AGE)
        else:
            response.delete_cookie('username')

        return response

    @staticmethod
    def login_failed(request, username, password):
        user = User.objects.filter(username=username).first()
        if user and user.check_password(password) and not user.is_active:
            return render(request, 'user/login.html', {
                'errmsg': '账户未激活',
                'username': username,
            })

        return render(request, 'user/login.html', {
            'errmsg': '账号或者密码错误',
            'username': username,
        })


def logout_view(request):
    session_key = request.session.session_key
    logout(request)

    if session_key:
        SessionStore(session_key=session_key).delete()

    return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiredMixin, View):
    """用户中心-个人信息"""

    def get(self, request):
        return render(request, 'user/user_center_info.html', {
            'page': 'user',
            'address': Address.objects.get_default_address(request.user),
            'goods_li': self.get_history_goods(request.user),
        })

    @staticmethod
    def get_history_goods(user):
        conn = get_redis_connection('default')
        sku_ids = conn.lrange('history_%d' % user.id, 0, 4)
        goods_li = []

        for sku_id in sku_ids:
            if isinstance(sku_id, bytes):
                sku_id = sku_id.decode()
            goods = GoodsSKU.objects.filter(id=sku_id).first()
            if goods:
                goods_li.append(goods)

        return goods_li


class UserOrderView(LoginRequiredMixin, View):
    """用户中心-订单信息"""

    status_filters = {
        'unpaid': [1],
        'paid': [2, 3, 4, 5],
        'uncomment': [4],
        'finished': [4, 5],  # status=4 的订单中也有已评价的商品
    }

    status_names = {
        1: '待支付',
        2: '已支付',
        3: '已支付',
        4: '待评价',
        5: '已评价',
    }

    def get(self, request, page=1):
        user = request.user
        status = self.get_status(request)
        orders = self.get_orders(user, status)
        order_items = self.make_order_items(orders, status)
        order_page, num_pages, _ = paginate(order_items, page, 4)

        return render(request, 'user/user_center_order.html', {
            'order_page': order_page,
            'num_pages': num_pages,
            'page': 'order',
            'status': status,
            'status_tabs': self.get_status_tabs(user),
        })

    def get_status(self, request):
        status = request.GET.get('status', 'all')
        if status == 'all' or status in self.status_filters:
            return status
        return 'all'

    def get_orders(self, user, status):
        orders = OrderInfo.objects.filter(user=user)
        if status != 'all':
            orders = orders.filter(order_status__in=self.status_filters[status])
        # 待评价(order_status=4)排最前面，其余按时间倒序
        return orders.annotate(
            is_uncomment=Case(
                When(order_status=4, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('is_uncomment', '-create_time')

    def get_status_tabs(self, user):
        all_ogs = OrderGoods.objects.filter(order__user=user)
        uncomment_count = all_ogs.filter(order__order_status=4, comment='').count()
        finished_count = all_ogs.exclude(comment='').count()
        return [
            {'key': 'all', 'name': '全部订单',
             'count': OrderInfo.objects.filter(user=user).count()},
            {'key': 'unpaid', 'name': '待支付',
             'count': OrderInfo.objects.filter(user=user, order_status=1).count()},
            {'key': 'paid', 'name': '已支付',
             'count': OrderInfo.objects.filter(user=user, order_status__in=[2, 3, 4, 5]).count()},
            {'key': 'uncomment', 'name': '待评价',
             'count': uncomment_count},
            {'key': 'finished', 'name': '已评价',
             'count': finished_count},
        ]

    def make_order_items(self, orders, status='all'):
        order_items = []

        for order in orders:
            order.status_name = self.status_names.get(
                order.order_status, OrderInfo.ORDER_STATUS[order.order_status]
            )
            og_qs = OrderGoods.objects.filter(order_id=order.order_id)

            # 按状态筛选商品条目
            if status == 'uncomment':
                og_qs = og_qs.filter(comment='')
            elif status == 'finished':
                og_qs = og_qs.exclude(comment='')

            # 未评论的商品排前面
            og_qs = og_qs.annotate(
                no_comment=Case(
                    When(comment='', then=0),
                    default=1,
                    output_field=IntegerField(),
                )
            ).order_by('no_comment', 'id')

            order.order_skus = og_qs
            for order_sku in og_qs:
                order_sku.amount = order_sku.count * order_sku.price
                order_items.append({
                    'order': order,
                    'order_sku': order_sku,
                    'status_name': order.status_name,
                    'total_pay': order_sku.amount + order.transit_price,
                })

        return order_items


class UserAddressView(LoginRequiredMixin, View):
    """用户中心-地址信息"""

    def get(self, request):
        return render(request, 'user/user_center_site.html', {
            'page': 'address',
            'addresses': Address.objects.filter(user=request.user).order_by('-is_default', '-id'),
        })

    def post(self, request):
        action = request.POST.get('action', 'add')
        user = request.user

        if action == 'set_default':
            addr_id = request.POST.get('addr_id')
            Address.objects.filter(user=user).update(is_default=False)
            Address.objects.filter(id=addr_id, user=user).update(is_default=True)
            return redirect(reverse('user:address'))

        if action == 'delete':
            addr_id = request.POST.get('addr_id')
            addr = Address.objects.filter(id=addr_id, user=user).first()
            if addr:
                was_default = addr.is_default
                addr.delete()
                if was_default:
                    new_default = Address.objects.filter(user=user).first()
                    if new_default:
                        new_default.is_default = True
                        new_default.save()
            return redirect(reverse('user:address'))

        # action == 'add'
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        if not all([receiver, addr, phone]):
            return render(request, 'user/user_center_site.html', {
                'page': 'address',
                'addresses': Address.objects.filter(user=user).order_by('-is_default', '-id'),
                'errmsg': '数据不完整',
            })
        if not re.match(PHONE_RE, phone):
            return render(request, 'user/user_center_site.html', {
                'page': 'address',
                'addresses': Address.objects.filter(user=user).order_by('-is_default', '-id'),
                'errmsg': '手机号格式错误',
            })

        Address.objects.create(
            user=user,
            receiver=receiver,
            addr=addr,
            zip_code=zip_code,
            phone=phone,
            is_default=not Address.objects.filter(user=user).exists(),
        )
        return redirect(reverse('user:address'))


class AccountCancelView(LoginRequiredMixin, View):
    """注销当前账号：彻底删除账号并退出登录。"""

    def post(self, request):
        user = request.user
        user_id = user.id

        conn = get_redis_connection('default')
        conn.delete('cart_%d' % user_id)
        conn.delete('history_%d' % user_id)

        logout(request)
        user.delete()
        return redirect(reverse('goods:index'))
