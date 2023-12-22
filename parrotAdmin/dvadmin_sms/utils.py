import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "application.settings")
django.setup()
from django.core.cache import cache

from application import dispatch
from dvadmin_sms.api.alibaba_cloud import AliBabaCloudSample
from dvadmin_sms.api.tencent_cloud import TencentCloudSample
from dvadmin.utils.validator import CustomValidationError


def send_sms(phone, code, send_type="mobilelogin"):
    """
    发送短信验证码
    :param phone: 手机号
    :param code: 验证码
    :param send_type: 发送类型 register/mobilelogin/changemobile/resetpwd/changepwd
    :return:
    """
    template_code = None

    for template in dispatch.get_system_config_values("sms.template"):
        if template.get('key') == send_type:
            template_code = template.get('value')
            break
    if not template_code:
        raise CustomValidationError('短信模板未找到')
    provider = dispatch.get_system_config_values("sms.provider") or False  # 服务商
    if provider == "aliyun":
        sample = AliBabaCloudSample(
            access_key_id=dispatch.get_system_config_values("sms.app_id"),
            access_key_secret=dispatch.get_system_config_values("sms.app_key")
        )
        return sample.send_sms(
            sign_name=dispatch.get_system_config_values("sms.signature") or '鹦鹉智学',
            template_code=template_code,
            phone_numbers=phone,
            template_param='{"code":"' + str(code) + '"}')

    elif provider == "tencent":
        sample = TencentCloudSample(
            access_key_id=dispatch.get_system_config_values("sms.app_id"),
            access_key_secret=dispatch.get_system_config_values("sms.app_key")
        )
        return sample.send_sms(sign_name=dispatch.get_system_config_values("sms.signature") or '鹦鹉智学',
                               template_code=template_code,
                               phone_numbers=phone,
                               template_param=str(code),
                               sms_sdk_app_id=dispatch.get_system_config_values("sms.sms_sdk_app_id"))
    elif provider == 'huawei':
        sample = None

    return False, "无效短信服务商"


def get_sms_code(phone):
    """
    获取已发送的短信验证码
    :param phone: 手机号
    :return:
    """
    return cache.get(f"dvadmin_sms_code_{phone}")


if __name__ == '__main__':
    template_code = send_sms('155362582917', '999999')
    print("template_code", template_code)
