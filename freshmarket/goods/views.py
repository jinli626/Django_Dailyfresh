from django.shortcuts import render,redirect
from django.urls import reverse
from django.views.generic import View
from .models import *
from django_redis import get_redis_connection
from order.models import *
from django.core.paginator import Paginator
#首页以及数据展示
class IndexView(View):
    def get(self,request):

        """获取商品的种类信息"""
        types = GoodsType.objects.all()  #全部商品分类

        """获取轮播图数据"""
        goods_banners = IndexGoodsBanner.objects.all().order_by('index')  #按照 index 进行排序

        # 获取首页促销活动信息
        promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

        # 首页专题专区
        featured_skus = GoodsSKU.objects.filter(status=1).order_by('-sales', '-id')[:6]
        lottery_skus = GoodsSKU.objects.filter(status=1).order_by('-id')[:3]





        """
        商品分类数据处理
        """



        #查询的时候，是根据商品分类GoodsType表 查询到 主页商品分类展示IndexTypeGoodsBanner表
        #查询条件是 type 字段相同
        #我们应该知道，主页商品分类信息中的商品分为两类，一个是图片链接类型，一个是文字链接类型
        #查询出来后，分别将两种类型的数据赋值给两个变量，这样就成功的提取出两种不同类型的商品数据
        #前端直接使用即可

        for type in types:  # GoodsType
            # 获取type种类首页分类商品的图片展示信息（数据是一个个图片商品信息，包括 文字、图片、价格、url 主要信息）
            image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')

            # 获取type种类首页分类商品的文字展示信息(数据是 文字 + 链接 类型，含有多个数据)
            title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')

            # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
            type.image_banners = image_banners
            type.title_banners = title_banners   #商品文字信息

        #从Redis中获取购物车商品总数
        #检查用户是否登录
        user = request.user

        #从 Redis数据库中获取用户购物车数据
        cart_count = 0  #未登录用户默认购物车数量为0
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            for count in conn.hvals(cart_key):
                cart_count += int(count)

        #组织上下文字典
        context = {'types': types,
                   'goods_banners': goods_banners,
                   'promotion_banners': promotion_banners,
                   'featured_skus': featured_skus,
                   'lottery_skus': lottery_skus,
                   'cart_count':cart_count}
        return render(request, 'index.html', context)



#详情页编写
class DetailView(View):
    def get(self,request,goods_id):  #根据商品id进入到指定商品的详情页
        # 查询下是否存在对应的商品
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))  #返回到首页

        #获取商品分类数据
        types = GoodsType.objects.all()

        #商品评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        #商品最新信息
        news_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        print(news_skus)
        #获取同一个商品的SPU的其它规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)



        # 购物车数据
        cart_count = 0  # 初始为0

        # 检查用户是否登录
        user = request.user
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            for count in conn.hvals(cart_key):
                cart_count += int(count)

            # 添加用户的浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id

            # 移除列表中的 goods_id
            conn.lrem(history_key, 0, goods_id)

            #把用户浏览的商品数据插入到列表左侧
            conn.lpush(history_key,goods_id)
            #保留用户最新浏览的5条记录
            conn.ltrim(history_key,0,4)


        context = {
            'types':types,
            'sku':sku,
            'sku_orders':sku_orders,
            'new_skus':news_skus,
            "same_spu_skus":same_spu_skus,
            'cart_count':cart_count
        }




        return render(request,'detail.html',context)




#list页面数据

class ListView(View):
    '''列表页'''
    def get(self, request, type_id, page):
        '''显示列表页'''
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 种类不存在
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()

        # 获取排序的方式 # 获取分类商品的信息
        # sort=default 按照默认id排序
        # sort=price 按照商品价格排序
        # sort=hot 按照商品销量排序
        sort = request.GET.get('sort')

        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 列表页一屏展示 8 个商品，避免商品很少时右侧大片空白还分页
        paginator = Paginator(skus, 8)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        skus_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
        # 1.总页数小于5页，页面上显示所有页码
        # 2.如果当前页是前3页，显示1-5页
        # 3.如果当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            for count in conn.hvals(cart_key):
                cart_count += int(count)

        # 组织模板上下文
        context = {'type':type, 'types':types,
                   'skus_page':skus_page,
                   'new_skus':new_skus,
                   'cart_count':cart_count,
                   'pages':pages,
                   'sort':sort}

        # 使用模板
        return render(request, 'list.html', context)


