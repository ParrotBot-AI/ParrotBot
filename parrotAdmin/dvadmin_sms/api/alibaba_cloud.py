"""阿里云api"""
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from application import settings


class AliBabaCloudSample:
    def __init__(self, access_key_id, access_key_secret):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret

    def sms_create_client(self) -> Dysmsapi20170525Client:
        """
        使用AK&SK初始化账号Client
        @param access_key_id:
        @param access_key_secret:
        @return: Client
        @throws Exception
        """
        config = open_api_models.Config(access_key_id=self.access_key_id, access_key_secret=self.access_key_secret)
        # 访问的域名
        config.endpoint = f'dysmsapi.aliyuncs.com'
        return Dysmsapi20170525Client(config)

    def send_sms(self, sign_name, template_code, phone_numbers, template_param) -> (bool, str):
        client = self.sms_create_client()
        send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
            sign_name=sign_name,
            template_code=template_code,
            phone_numbers=phone_numbers,
            template_param=template_param
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            res = client.send_sms_with_options(send_sms_request, runtime)
            if res.body.code == "OK":
                return True, ""
            return False, res.body.message
        except Exception as error:
            # 如有需要，请打印 error
            print(error)
            return False, UtilClient.assert_as_string(error)