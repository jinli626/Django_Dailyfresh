import os
import time
from datetime import datetime

from alipay import AliPay
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from goods.models import GoodsSKU
from order.models import OrderGoods, OrderInfo
from user.models import Address
from utils.common import cart_key, get_cart_skus, json_login_required, redis_conn
from utils.mixin import LoginRequiredMixin

ALIPAY_APP_ID = '9021000164696803'
ALIPAY_GATEWAY = 'https://openapi-sandbox.dl.alipaydev.com/gateway.do?'
TRANSIT_PRICE = 10


def get_alipay_client():
    private_key_path = os.path.join(settings.BASE_DIR, 'order/app_private_key.pem')
    public_key_path = os.path.join(settings.BASE_DIR, 'order/alipay_public_key.pem')

    with open(private_key_path) as f:
        app_private_key_string = f.read()
    with open(public_key_path) as f:
        alipay_public_key_string = f.read()

    return AliPay(
        appid=ALIPAY_APP_ID,
        app_notify_url=None,
        app_private_key_string=app_private_key_string,
        alipay_public_key_string=alipay_public_key_string,
        sign_type='RSA2',
        debug=True
    )


class OrderPlaceView(LoginRequiredMixin, View):
    """提交订单确认页"""

    def post(self, request):
        sku_ids = request.POST.getlist('sku_ids')
        if not sku_ids:
            return redirect(reverse('cart:show'))

        skus, total_count, total_price = get_cart_skus(request.user, sku_ids)
        return render(request, 'place_order.html', {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': TRANSIT_PRICE,
            'total_pay': total_price + TRANSIT_PRICE,
            'addrs': Address.objects.filter(user=request.user),
            'sku_ids': ','.join(sku_ids),
        })


class OrderCommitView1(View):
    """创建订单"""

    @json_login_required
    @transaction.atomic
    def post(self, request):
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})
        if pay_method not in OrderInfo.PAY_METHODS:
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址不存在'})

        save_id = transaction.savepoint()
        sku_id_list = sku_ids.split(',')

        try:
            order = self.create_order(request.user, addr, pay_method)
            total_count, total_price = self.create_order_goods(order, request.user, sku_id_list, save_id)
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except ValueError as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse(e.args[0])
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败: %s' % str(e)})

        transaction.savepoint_commit(save_id)
        redis_conn().hdel(cart_key(request.user), *sku_id_list)
        return JsonResponse({'res': 5, 'message': '创建成功'})

    @staticmethod
    def create_order(user, addr, pay_method):
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        return OrderInfo.objects.create(
            order_id=order_id,
            user=user,
            addr=addr,
            pay_method=pay_method,
            total_count=0,
            total_price=0,
            transit_price=TRANSIT_PRICE,
        )

    def create_order_goods(self, order, user, sku_ids, save_id):
        conn = redis_conn()
        key = cart_key(user)
        total_count = 0
        total_price = 0

        for sku_id in sku_ids:
            count = conn.hget(key, sku_id)
            sku, count = self.reduce_stock(sku_id, count, save_id)

            OrderGoods.objects.create(order=order, sku=sku, count=count, price=sku.price)
            total_count += count
            total_price += sku.price * count

        return total_count, total_price

    @staticmethod
    def reduce_stock(sku_id, count, save_id):
        try:
            count = int(count)
        except (TypeError, ValueError):
            raise ValueError({'res': 1, 'errmsg': '参数不完整'})

        for retry in range(3):
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                raise ValueError({'res': 4, 'errmsg': '商品不存在'})

            if count > sku.stock:
                raise ValueError({'res': 6, 'errmsg': ' 商品库存不足'})

            old_stock = sku.stock
            updated = GoodsSKU.objects.filter(id=sku_id, stock=old_stock).update(
                stock=old_stock - count,
                sales=sku.sales + count
            )
            if updated:
                return sku, count
            if retry == 2:
                raise ValueError({'res': 7, 'errmsg': '下单失败2'})

        raise ValueError({'res': 7, 'errmsg': '下单失败2'})


class OrderPayView(View):
    """订单支付"""

    @json_login_required
    def post(self, request):
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单编号不存在'})

        order = self.get_unpaid_order(request.user, order_id)
        if order is None:
            return JsonResponse({'res': 2, 'errmsg': '无效订单'})

        try:
            alipay = get_alipay_client()
        except Exception as e:
            return JsonResponse({'res': 4, 'errmsg': '支付宝配置错误: %s' % str(e)})

        total_pay = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(total_pay),
            subject='天天生鲜订单-%s' % order_id,
            return_url=request.build_absolute_uri(reverse('user:order', kwargs={'page': 1})),
            notify_url=None
        )
        return JsonResponse({'res': 3, 'pay_url': ALIPAY_GATEWAY + order_string})

    @staticmethod
    def get_unpaid_order(user, order_id):
        return OrderInfo.objects.filter(
            order_id=order_id,
            user=user,
            pay_method=3,
            order_status=1
        ).first()


class MockPayView(View):
    """开发环境模拟支付成功"""

    @json_login_required
    def post(self, request):
        if not settings.DEBUG:
            return JsonResponse({'res': 4, 'errmsg': '模拟支付只允许在开发环境使用'})

        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单编号不存在'})

        order = OrderInfo.objects.filter(order_id=order_id, user=request.user, order_status=1).first()
        if order is None:
            return JsonResponse({'res': 2, 'errmsg': '无效订单'})

        order.trade_no = 'mock_%s' % datetime.now().strftime('%Y%m%d%H%M%S')
        order.order_status = 4
        order.save()
        return JsonResponse({'res': 3, 'message': '模拟支付成功'})


class CheckPayView(OrderPayView):
    """查询支付宝支付结果"""

    @json_login_required
    def post(self, request):
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单编号不存在'})

        order = self.get_unpaid_order(request.user, order_id)
        if order is None:
            return JsonResponse({'res': 2, 'errmsg': '无效订单'})

        try:
            alipay = get_alipay_client()
        except Exception as e:
            return JsonResponse({'res': 4, 'errmsg': '支付宝配置错误: %s' % str(e)})

        while True:
            response = alipay.api_alipay_trade_query(order_id)
            code = response.get('code')
            trade_status = response.get('trade_status')

            if code == '10000' and trade_status == 'TRADE_SUCCESS':
                order.trade_no = response.get('trade_no')
                order.order_status = 4
                order.save()
                return JsonResponse({'res': 3, 'message': '支付成功'})

            if code == '40004' or (code == '10000' and trade_status == 'WAIT_BUYER_PAY'):
                time.sleep(5)
                continue

            return JsonResponse({'res': 4, 'errmsg': '支付失败'})


class CommentView(LoginRequiredMixin, View):
    """订单评论"""

    def get(self, request, order_id, order_goods_id=None):
        order = self.get_user_order(request.user, order_id)
        if order is None:
            return redirect(reverse('user:order', kwargs={'page': 1}))

        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        if order_goods_id is None:
            return self.redirect_first_uncommented(order, order_id)

        order_sku = OrderGoods.objects.filter(id=order_goods_id, order=order).first()
        if order_sku is None:
            return redirect(reverse('user:order', kwargs={'page': 1}))

        order_sku.amount = order_sku.count * order_sku.price
        remaining_count = OrderGoods.objects.filter(order=order, comment='').exclude(id=order_sku.id).count()
        return render(request, 'order_comment.html', {
            'order': order,
            'order_sku': order_sku,
            'remaining_count': remaining_count
        })

    def post(self, request, order_id, order_goods_id=None):
        order = self.get_user_order(request.user, order_id)
        if order is None:
            return redirect(reverse('user:order', kwargs={'page': 1}))

        if order_goods_id is None:
            self.save_old_comment_form(request, order)
        else:
            order_goods = OrderGoods.objects.filter(id=order_goods_id, order=order).first()
            if order_goods is None:
                return redirect(reverse('user:order', kwargs={'page': 1}))
            order_goods.comment = request.POST.get('content', '')
            order_goods.save()

        order.order_status = 4 if OrderGoods.objects.filter(order=order, comment='').exists() else 5
        order.save()
        return redirect(reverse('user:order', kwargs={'page': 1}))

    @staticmethod
    def get_user_order(user, order_id):
        if not order_id:
            return None
        return OrderInfo.objects.filter(order_id=order_id, user=user).first()

    @staticmethod
    def redirect_first_uncommented(order, order_id):
        order_goods = OrderGoods.objects.filter(order=order, comment='').first()
        if order_goods is None:
            return redirect(reverse('user:order', kwargs={'page': 1}))

        return redirect(reverse('order:comment_item', kwargs={
            'order_id': order_id,
            'order_goods_id': order_goods.id
        }))

    @staticmethod
    def save_old_comment_form(request, order):
        total_count = int(request.POST.get('total_count', 0))

        for index in range(1, total_count + 1):
            sku_id = request.POST.get('sku_%d' % index)
            order_goods = OrderGoods.objects.filter(order=order, sku_id=sku_id).first()
            if order_goods is None:
                continue

            order_goods.comment = request.POST.get('content_%d' % index, '')
            order_goods.save()
