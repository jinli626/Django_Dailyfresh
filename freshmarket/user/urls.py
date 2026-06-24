from django.contrib.auth.decorators import login_required
from django.urls import re_path

from user.views import (
    AccountCancelView,
    ActiveView,
    LoginView,
    RegisterView,
    UserAddressView,
    UserInfoView,
    UserOrderView,
    logout_view,
)


app_name = 'user'

urlpatterns = [
    re_path(r'^register$', RegisterView.as_view(), name='register'),
    re_path(r'^login$', LoginView.as_view(), name='login'),
    re_path(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    re_path(r'^$', UserInfoView.as_view(), name='user'),
    re_path(r'^order$', login_required(UserOrderView.as_view()), name='order'),
    re_path(r'^address$', UserAddressView.as_view(), name='address'),
    re_path(r'^logout$', logout_view, name='logout'),
    re_path(r'^cancel$', AccountCancelView.as_view(), name='cancel'),
    re_path(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),
]
