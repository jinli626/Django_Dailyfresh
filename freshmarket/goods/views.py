from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import View

from goods.models import (
    GoodsSKU,
    GoodsType,
    IndexGoodsBanner,
    IndexPromotionBanner,
    IndexTypeGoodsBanner,
)
from order.models import OrderGoods
from utils.common import cart_total_count, paginate, redis_conn, simple_pages


class IndexView(View):
    """首页"""

    def get(self, request):
        types = GoodsType.objects.all()

        for goods_type in types:
            goods_type.image_banners = IndexTypeGoodsBanner.objects.filter(
                type=goods_type,
                display_type=1
            ).order_by('index')
            goods_type.title_banners = IndexTypeGoodsBanner.objects.filter(
                type=goods_type,
                display_type=0
            ).order_by('index')

        return render(request, 'goods/index.html', {
            'types': types,
            'goods_banners': IndexGoodsBanner.objects.all().order_by('index'),
            'promotion_banners': IndexPromotionBanner.objects.all().order_by('index'),
            'featured_skus': GoodsSKU.objects.filter(status=1).order_by('-sales', '-id')[:6],
            'lottery_skus': GoodsSKU.objects.filter(status=1).order_by('-id')[:3],
            'cart_count': cart_total_count(request.user),
        })


class DetailView(View):
    """商品详情页"""

    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))

        if request.user.is_authenticated:
            self.save_history(request.user, goods_id)

        return render(request, 'goods/detail.html', {
            'types': GoodsType.objects.all(),
            'sku': sku,
            'sku_orders': OrderGoods.objects.filter(sku=sku).exclude(comment=''),
            'new_skus': GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2],
            'same_spu_skus': GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id),
            'cart_count': cart_total_count(request.user),
        })

    @staticmethod
    def save_history(user, goods_id):
        conn = redis_conn()
        key = 'history_%d' % user.id
        conn.lrem(key, 0, goods_id)
        conn.lpush(key, goods_id)
        conn.ltrim(key, 0, 4)


class ListView(View):
    """商品列表页"""

    def get(self, request, type_id, page):
        try:
            goods_type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        sort = request.GET.get('sort', 'default')
        skus = self.get_skus(goods_type, sort)
        skus_page, num_pages, page = paginate(skus, page, 8)

        return render(request, 'goods/list.html', {
            'type': goods_type,
            'types': GoodsType.objects.all(),
            'skus_page': skus_page,
            'new_skus': GoodsSKU.objects.filter(type=goods_type).order_by('-create_time')[:2],
            'cart_count': cart_total_count(request.user),
            'pages': simple_pages(page, num_pages),
            'sort': sort if sort in ['price', 'hot'] else 'default',
        })

    @staticmethod
    def get_skus(goods_type, sort):
        skus = GoodsSKU.objects.filter(type=goods_type)

        if sort == 'price':
            return skus.order_by('price')
        if sort == 'hot':
            return skus.order_by('-sales')
        return skus.order_by('-id')
