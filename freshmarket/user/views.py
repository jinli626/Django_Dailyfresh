import re
from email.utils import formataddr
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.shortcuts import render, redirect
from .models import *
from django.views.generic import View
from itsdangerous import URLSafeTimedSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from django.http import HttpResponse
from django.core.mail import send_mail

from celery_tasks.tasks import send_register_active_email
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from order.models import *

from goods.models import *


# 显示注册页面

class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        """接收表单数据"""
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')  # 如果被选中，获取的值是 on
        confirm_password = request.POST.get('cpwd')  # 确认密码

        """数据校验"""
        if not all([username, password, email, allow]):
            return render(request, 'register.html', {"errmsg": "数据不完整"})  # 数据不完整

        """邮箱校验"""
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {"errmsg": "邮箱格式不正确！"})

        """是否勾选协议"""
        if allow != "on":
            return render(request, 'register.html', {"errmsg": "请勾选协议"})

        """校验用户名是否重复"""

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在，可用
            user = None

        if user:
            # 用户名存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 检查密码是否一致
        if password != confirm_password:
            return render(request, 'register.html', {'errmsg': '两次输入的密码不一致'})

        """全部通过，校验数据"""

        user = User.objects.create_user(username, email, password)

        # 设置默认为未激活状态
        user.is_active = 0
        user.save()

        # 激活链接设置
        # 发送激活邮件，包含激活连接： http：//127.0.0.1：8000/user/active/用户id
        # 激活连接中需要包含用户的身份信息，并且要把身份信息进行加密处理

        serializer = Serializer(settings.SECRET_KEY, 3600)  # 设置加密对象，有效时间为 1h
        info = {'confirm': user.id}
        token = serializer.dumps(info)  # 对id值进行加密
        token = token.decode('utf8')

        # 发送邮件，现在切换成异步处理任务，在 Celery 文件中编写好后，直接调用传参即可
        send_register_active_email.delay(to_email=email, username=username, token=token)  # 需要三个参数

        # 返回到首页
        return redirect(reverse('goods:index'))


# 在完成激活功能之前，我们应该把用户设置为未激活状态
# 先修改下代码


# 激活视图类
class ActiveView(View):
    def get(self, request, token):
        """进行解密，获取要激活的用户信息"""
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)  # 解密
            user_id = info['confirm']  # 获取id

            # 查询处指定用户，并设置 is_active 的值为1，完成激活
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 返回到登录页面
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            return HttpResponse("激活链接已经失效！")


# 返回登录界面

class LoginView(View):
    def get(self, request):
        """判断是否记住了用户名"""
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    # 定义 POST 请求
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 进行数据校验
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': "账号或者密码不能为空"})

        """
        只有当账号密码正确，并且 is_active=True 的时候，函数才会返回用户对象，否则是 None
        所以采用下面的方式进行验证用户是否被激活
        """
        user = authenticate(username=username, password=password)

        # 激活成功的用户
        if user is not None:
            login(request, user)

            # 获取登录后要跳转的地址，现在是登录后自动跳转到首页，假如用户直接访问 address ，登录后
            # 我们应该让其返回到 address 这个页面

            next_url = request.GET.get('next', reverse('goods:index'))  # 默认是首页

            # 重定向网页可以先用一个变量接收，这样可以不用立即进行重定向，后面直接
            # return 变量 即可完成重定向操作
            response = redirect(next_url)

            # 判断用户是否点击了 记住用户
            # 点击后，将 username 存储到 cookie 中，下次登录时，直接从 cookie 中获取用户名天从到表单中
            # 不需要用户重复输入用户名
            remember = request.POST.get('remember')

            # 点击记住用户
            if remember == "on":
                response.set_cookie('username', username, max_age=7 * 24 * 36)
            else:
                response.delete_cookie('username')

            return response


        # 当函数 authenticate() 返回 None时，验证下是是账号或者密码错误，还是用户未激活
        else:
            # 进一步判断用户是否存在，但未激活
            try:
                user = User.objects.get(username=username)
                if not user.check_password(password):
                    raise User.DoesNotExist  # 密码不对也当成查不到
                if not user.is_active:
                    return render(request, 'login.html', {'errmsg': "账户未激活"})
            except User.DoesNotExist:
                pass

            return render(request, 'login.html', {'errmsg': '账号或者密码错误'})


# 退出登录
from django.contrib.auth import logout
from django_redis import get_redis_connection

from django.contrib.auth import logout
from django_redis import get_redis_connection
from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore


def logout_view(request):
    session_key = request.session.session_key
    logout(request)

    if session_key:
        store = SessionStore(session_key=session_key)
        store.delete()  # 调用 SessionStore.delete() 会删除缓存中的 session

    return redirect(reverse('goods:index'))


# 现在开始编写 用户中心-个人信息、用户中心-订单信息、用户中心-地址信息

# user-用户信息
class UserInfoView(LoginRequiredMixin, View):
    def get(self, request):
        # 获取用户个人信息
        user = request.user
        address = Address.objects.get_default_address(request.user)

        # 用户最近浏览记录
        # 创建连接对象
        conn = get_redis_connection('default')
        history_key = 'history_%d' % user.id  # 用户浏览记录对应的id

        # 获取用户最新浏览的5个商品的id
        sku_ids = conn.lrange(history_key, 0, 4)

        # 从数据库中查询用户浏览的商品的具体信息
        goods_li = []

        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)  # 将用户浏览商品信息添加到列表中，一个 goods 是一个查询结果集合

        # 组织上下文，将所有的字典信息添加到同一个变量中
        context = {
            'page': 'user',
            'address': address,
            'goods_li': goods_li  # 商品信息
        }

        # {'page':'user'} 用来判断是否在当前页，显示对应的颜色
        return render(request, 'user_center_info.html', context)


# user-订单信息
class UserOrderView(LoginRequiredMixin, View):
    """用户中心-信息页"""

    def get(self, request, page=1):  # 无页码时默认第1页，兼容 /user/order 和 /user/order/1
        """显示"""
        # 获取用户的订单信息
        user = request.user
        status = request.GET.get('status', 'all')
        status_filters = {
            'unpaid': [1],
            'paid': [2, 3, 4, 5],
            'uncomment': [4],
            'finished': [5],
        }
        status_tabs = [
            {'key': 'all', 'name': '全部订单', 'count': OrderInfo.objects.filter(user=user).count()},
            {'key': 'unpaid', 'name': '待支付', 'count': OrderInfo.objects.filter(user=user, order_status=1).count()},
            {'key': 'paid', 'name': '已支付',
             'count': OrderInfo.objects.filter(user=user, order_status__in=[2, 3, 4, 5]).count()},
            {'key': 'uncomment', 'name': '待评价',
             'count': OrderInfo.objects.filter(user=user, order_status=4).count()},
            {'key': 'finished', 'name': '已评价', 'count': OrderInfo.objects.filter(user=user, order_status=5).count()},
        ]
        if status not in status_filters and status != 'all':
            status = 'all'

        orders = OrderInfo.objects.filter(user=user)
        if status != 'all':
            orders = orders.filter(order_status__in=status_filters[status])
        orders = orders.order_by('-create_time')

        order_items = []
        order_status_names = {
            1: '待支付',
            2: '已支付',
            3: '已支付',
            4: '待评价',
            5: '已评价',
        }
        # 便利获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 便利order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count * order_sku.price
                # 动态给order_sku增加属性amount，保存订单商品的小计
                order_sku.amount = amount
            order.status_name = order_status_names.get(order.order_status, OrderInfo.ORDER_STATUS[order.order_status])
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus
            for order_sku in order_skus:
                order_items.append({
                    'order': order,
                    'order_sku': order_sku,
                    'status_name': order.status_name,
                    'total_pay': order_sku.amount + order.transit_price,
                })

        # 分页：每页展示多条订单，避免页码过多、列表过空
        paginator = Paginator(order_items, 4)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        num_pages = paginator.num_pages

        # 组织上下文
        context = {'order_page': order_page,
                   'num_pages': num_pages,
                   'page': 'order',
                   'status': status,
                   'status_tabs': status_tabs}

        return render(request, 'user_center_order.html', context)


# user-地址信息
class UserAddressView(LoginRequiredMixin, View):
    def get(self, request):
        # 返默认地址
        user = request.user  # 这个是自动有的
        address = Address.objects.get_default_address(user)

        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        """接收数据"""
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        print(receiver, addr, zip_code, phone)

        """校验数据,因为邮编可以为空，所以这里部将其加入到校验数据中"""
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': "数据不完整"})

        print("测试中")

        print(f"手机号是：{phone}")
        """检验手机号"""
        if not re.match(r'^1[34578]\d{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': "手机号格式错误"})

        """
        默认地址
        如果已经存在默认地址，则新添加到地址不设置为默认地址
        """

        """地址属于用户，根据登录对象获取用户对象，然后查询出对应的地址信息，
        使用 user = request.user 作为查询条件很常见，一般用于查询属于用户的数据,并进行相应的操作
        """
        user = request.user  # 这个是自动有的

        address = Address.objects.get_default_address(user)

        # 根据查询结果设置 is_default 的值，True（代表存在默认），False（无默认地址）
        if address:
            is_default = False
        else:
            is_default = True

        print(1111111111111111)
        Address.objects.create(
            user=user,
            receiver=receiver,
            addr=addr,
            zip_code=zip_code,
            phone=phone,
            is_default=is_default
        )

        # 刷新网页
        return redirect(reverse('user:address'))
