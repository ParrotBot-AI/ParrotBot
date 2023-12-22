import random

from django.core.cache import cache
from rest_framework.views import APIView

from application import dispatch
from dvadmin.utils.json_response import ErrorResponse, DetailResponse
from dvadmin_sms.utils import send_sms


class SmsSendSmsView(APIView):
    """
    发送验证码
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """
        发送验证码
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        phone = request.data.get('phone')
        print(dispatch.get_system_config_values("sms.provider"))
        # 校验手机号是否正确
        if len(phone) != 11:
            return ErrorResponse(msg=f"请输入正确的手机号!")

        is_enabled = dispatch.get_system_config_values("sms.is_enabled") or False  # 是否启用短信服务
        if not is_enabled:
            return ErrorResponse(msg=f"暂未开启短信服务!")
        frequency = dispatch.get_system_config_values("sms.frequency") or 60  # 短信发送频率

        test_white_list = dispatch.get_system_config_values("sms.test_white_list") or ''  # 测试白名单手机号
        is_send_sms = cache.get(f"dvadmin_sms_send_sms_{phone}")
        if is_send_sms:
            return ErrorResponse(msg=f"{frequency}秒内只能发送一次!")
        # 判断是否是测试白名单手机号
        if phone in test_white_list.split(','):
            code = 999999
        else:
            code = random.randint(100000, 999999)
            # 发送手机号登录验证码
            status, msg = send_sms(phone=phone, code=code, send_type="mobilelogin")
            if not status:
                return ErrorResponse(msg=f"发送失败，请联系管理员!")
        cache.set(f"dvadmin_sms_send_sms_{phone}", code, frequency)
        cache.set(f"dvadmin_sms_code_{phone}", code, 300)  # 5分钟有效期
        return DetailResponse(msg=f"发送成功!")
