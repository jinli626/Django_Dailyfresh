from django.shortcuts import render
from django.views.generic import View

from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
# Create your views here.

# /cart/add


#加入购物车功能
class CartAddView(View):
    def post(self,request):
        user = request.user
        #检查是否登录
        if not user.is_authenticated:
            return JsonResponse({'res':0, 'errmsg':'请先登录'})

        #接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        #数据校验
        if not all([sku_id,count]):
            return JsonResponse('res',1,{'errmsg':"数据不完整"})

        #校验添加商品的数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        #检查商品是否存在
        #下面是检查数据库中数据是否存在的常用方法
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})


        #将商品添加到购物车中
        conn = get_redis_connection('default')  #Redis 连接对象
        cart_key ='cart_%d' % user.id

        #检查要添加到商品是否已经存在于 Redis 中，如果存在，进行累加
        cart_count = conn.hget(cart_key,sku_id)
        if cart_count:
            count += int(cart_count)

        #检查下是否超过库存
        if count > sku.stock:
            return JsonResponse({'res':4, 'errmsg':'商品库存不足'})

        #将数据添加到 Redis 中
        conn.hset(cart_key,sku_id,count)

        #获取购物车总数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        #返回应答
        return JsonResponse({'res':5, 'total_count': total_count, 'message':'添加成功'})



#购物车数据显示---Redis 中获取数据
class CartInfoView(LoginRequiredMixin, View):
    def get(self,request):
        """从Redis中获取数据"""
        user = request.user

        #获取数据
        conn = get_redis_connection('default')
        #构造键名 key,使用字符串格式化写法
        cart_key ='cart_%d' % user.id  #'cart_%d' % x	把整数 x 插入 %d 所在位置，生成字符串

        #根据键名获取数据获取数据，数据结构为字典类型 {'商品id':商品数量}
        cart_dict = conn.hgetall(cart_key)

        #创建列表存储购物车中所有商品的详细数据
        skus = []
        # 保存用户购物从中商品的总数和总价
        total_count = 0
        total_price = 0

        for sku_id,count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)  #根据商品id获取商品信息
            amount = sku.price * int(count)  #商品小计，价格乘以数量

            #动态给商品实例添加属性 amount ，保存小计
            sku.amount = amount

            #动态增加属性，保存购物车数量
            sku.count = int(count)

            #添加到列表中
            skus.append(sku)

            #对商品总数和总价进行累加
            total_count += int(count)
            total_price += amount

            #组织上下文
        context={


            'total_count':total_count,
            'total_price':total_price,
            'skus':skus

            }

        #返回网页
        return render(request,'cart.html',context)



#接下来是更新数据
#在购物车中，点击 + - 商品数量，涉及到 Redis 数据修改，因此结合前端的 Ajax 技术，发起 POST 请求，
#完成数据更新


class CartUpdateView(View):
    def post(self,request):
        """检查用户是否已经登录"""
        user = request.user
        if not user.is_authenticated:
            return  JsonResponse({'res':0,'errmsg':"请先登录"})

        #接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        #数据校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':"数据不完整"})

        #检验添加商品的数量
        try:
            count = int(count)
        except Exception as e:
            return  JsonResponse({'res':2,'errmsg':"商品数量出错"})

        #检查商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return  JsonResponse({'res':3,'errmsg':"商品不存在"})

        #业务逻辑---更新购物车数据
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        #校验商品库存
        if count > sku.stock:
            return JsonResponse({'res':4,'errmsg':"库存不足"})

        #更新
        conn.hset(cart_key,sku_id,count)

        #返回应答
        return  JsonResponse({'res':5,'errmsg':"更新成功!"})



#现在完成删除购物车商品
class CartDeleteView(View):
    def post(self,request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res':0,'errmsg':"请先登录"})

        sku_id = request.POST.get('sku_id')

        #校验商品id是否有效
        if not sku_id:
            return JsonResponse({'res':1,'errmsg':"无效的商品id"})

        #检查商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': "商品不存在"})

        #业务逻辑---删除商品
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key,sku_id)

        #计算购物车中的商品条目数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res':3,'total_count':total_count,'message':"删除成功"})










        

















































