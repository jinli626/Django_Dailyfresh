from django_redis import get_redis_connection


def cart_count(request):
    count = 0
    user = getattr(request, 'user', None)

    if user and user.is_authenticated:
        conn = get_redis_connection('default')
        cart_key = f'cart_{user.id}'
        for value in conn.hvals(cart_key):
            count += int(value)

    return {'cart_count': count}
