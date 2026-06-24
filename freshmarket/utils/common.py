from functools import wraps

from django.core.paginator import Paginator
from django.http import JsonResponse
from django_redis import get_redis_connection

from goods.models import GoodsSKU


def json_login_required(func):
    """AJAX接口登录校验：未登录时返回原项目约定的 res=0。"""

    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        return func(self, request, *args, **kwargs)

    return wrapper


def redis_conn():
    return get_redis_connection('default')


def cart_key(user):
    return 'cart_%d' % user.id


def cart_total_count(user):
    if not user.is_authenticated:
        return 0

    conn = redis_conn()
    return sum(int(count) for count in conn.hvals(cart_key(user)))


def get_cart_skus(user, sku_ids=None):
    """返回购物车商品列表、总数量、总价格。

    sku_ids 为空时读取整个购物车；不为空时只读取指定商品，供下单确认页使用。
    """
    conn = redis_conn()
    key = cart_key(user)
    cart_dict = conn.hgetall(key)

    if sku_ids is None:
        sku_ids = cart_dict.keys()

    skus = []
    total_count = 0
    total_price = 0

    for sku_id in sku_ids:
        if isinstance(sku_id, bytes):
            sku_id = sku_id.decode()

        count = cart_dict.get(str(sku_id).encode()) or cart_dict.get(str(sku_id))
        if count is None:
            continue

        sku = GoodsSKU.objects.get(id=sku_id)
        count = int(count)
        sku.count = count
        sku.amount = sku.price * count

        skus.append(sku)
        total_count += count
        total_price += sku.amount

    return skus, total_count, total_price


def safe_page_number(page, paginator):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1

    if page < 1 or page > paginator.num_pages:
        page = 1

    return page


def paginate(data, page, per_page):
    paginator = Paginator(data, per_page)
    page = safe_page_number(page, paginator)
    return paginator.page(page), paginator.num_pages, page


def simple_pages(current_page, num_pages, max_count=5):
    if num_pages <= max_count:
        return range(1, num_pages + 1)

    half = max_count // 2
    if current_page <= half + 1:
        return range(1, max_count + 1)

    if num_pages - current_page <= half:
        return range(num_pages - max_count + 1, num_pages + 1)

    return range(current_page - half, current_page + half + 1)
