
from django.contrib import admin
from django.urls import path,include,re_path
from .views import *

app_name = 'order'

urlpatterns = [
    re_path(r'^place$', OrderPlaceView.as_view(), name='place'), # 提交订单页面显示
    re_path(r'^commit$', OrderCommitView1.as_view(), name='commit'), # 提交创建
    re_path(r'^pay$', OrderPayView.as_view(), name='pay'), # 订单支付
    re_path(r'^mock_pay$', MockPayView.as_view(), name='mock_pay'), # 开发环境模拟支付
    re_path(r'^check$', CheckPayView.as_view(), name='check'), # 查询支付订单结果
    re_path(r'^comment/(?P<order_id>[^/]+)/(?P<order_goods_id>\d+)$', CommentView.as_view(), name='comment_item'), # 单个商品评论
    re_path(r'^comment/(?P<order_id>.+)$', CommentView.as_view(), name='comment'), # 订单评论



]
