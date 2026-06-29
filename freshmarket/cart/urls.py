from django.urls import re_path

from cart.views import CartAddView, CartDeleteView, CartInfoView, CartUpdateView


urlpatterns = [
    re_path(r'^add/$', CartAddView.as_view(), name='add'),
    re_path(r'^$', CartInfoView.as_view(), name='show'),
    re_path(r'^update/$', CartUpdateView.as_view(), name='update'),
    re_path(r'^delete/$', CartDeleteView.as_view(), name='delete'),
]
