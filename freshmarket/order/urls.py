from django.urls import re_path

from order.views import (
    CheckPayView,
    CommentView,
    MockPayView,
    OrderCommitView,
    OrderPayView,
    OrderPlaceView,
)


app_name = 'order'

urlpatterns = [
    re_path(r'^place$', OrderPlaceView.as_view(), name='place'),
    re_path(r'^commit$', OrderCommitView.as_view(), name='commit'),
    re_path(r'^pay$', OrderPayView.as_view(), name='pay'),
    re_path(r'^mock_pay$', MockPayView.as_view(), name='mock_pay'),
    re_path(r'^check$', CheckPayView.as_view(), name='check'),
    re_path(r'^comment/(?P<order_id>[^/]+)/(?P<order_goods_id>\d+)$', CommentView.as_view(), name='comment_item'),
    re_path(r'^comment/(?P<order_id>.+)$', CommentView.as_view(), name='comment'),
]
