from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import View

from goods.models import GoodsSKU
from utils.common import cart_key, cart_total_count, get_cart_skus, json_login_required, redis_conn


class CartAddView(View):
    """加入购物车"""

    @json_login_required
    def post(self, request):
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            count = int(count)
            sku = GoodsSKU.objects.get(id=sku_id)
        except ValueError:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        conn = redis_conn()
        key = cart_key(request.user)
        old_count = conn.hget(key, sku_id)
        count += int(old_count) if old_count else 0

        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

        conn.hset(key, sku_id, count)
        return JsonResponse({
            'res': 5,
            'total_count': cart_total_count(request.user),
            'message': '添加成功'
        })


class CartInfoView(LoginRequiredMixin, View):
    """购物车页面"""

    def get(self, request):
        skus, total_count, total_price = get_cart_skus(request.user)
        return render(request, 'cart/cart.html', {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
        })


class CartUpdateView(View):
    """更新购物车商品数量"""

    @json_login_required
    def post(self, request):
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            count = int(count)
            sku = GoodsSKU.objects.get(id=sku_id)
        except ValueError:
            return JsonResponse({'res': 2, 'errmsg': '商品数量出错'})
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})

        conn = redis_conn()
        key = cart_key(request.user)
        conn.hset(key, sku_id, count)
        total_count = sum(int(c) for c in conn.hvals(key))
        return JsonResponse({'res': 5, 'total_count': total_count, 'errmsg': '更新成功!'})


class CartDeleteView(View):
    """删除购物车商品"""

    @json_login_required
    def post(self, request):
        sku_id = request.POST.get('sku_id')
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的商品id'})

        if not GoodsSKU.objects.filter(id=sku_id).exists():
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        redis_conn().hdel(cart_key(request.user), sku_id)
        return JsonResponse({
            'res': 3,
            'total_count': cart_total_count(request.user),
            'message': '删除成功'
        })
