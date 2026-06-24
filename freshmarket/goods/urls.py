from django.urls import path, re_path

from goods.views import DetailView, IndexView, ListView

app_name = 'goods'

urlpatterns = [
    re_path(r'^index$', IndexView.as_view(), name='index'),
    re_path(r'^goods/(?P<goods_id>\d+)$', DetailView.as_view(), name='detail'),
    path('list/<int:type_id>/<int:page>/', ListView.as_view(), name='list'),
]
