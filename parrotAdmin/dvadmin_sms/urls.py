from rest_framework import routers
from django.urls import re_path

from dvadmin_sms.views.send_sms import SmsSendSmsView

router_url = routers.SimpleRouter()
urlpatterns = [
    # 发送短信
    re_path(r'^send_login_sms/$',SmsSendSmsView.as_view()),
]
urlpatterns += router_url.urls
