"""腾讯云api"""
import json

from tencentcloud.common import credential
from tencentcloud.sms.v20210111 import sms_client, models


class TencentCloudSample:
    def __init__(self, access_key_id, access_key_secret):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        cred = credential.Credential(access_key_id, access_key_secret)
        self.client = sms_client.SmsClient(cred, "ap-beijing")

    def send_sms(self, sign_name, template_code, phone_numbers, template_param, sms_sdk_app_id) -> (bool, str):
        req = models.SendSmsRequest()
        # 短信应用ID: 短信SdkAppId在 [短信控制台] 添加应用后生成的实际SdkAppId，示例如1400006666
        # 应用 ID 可前往 [短信控制台](https://console.cloud.tencent.com/smsv2/app-manage) 查看
        req.SmsSdkAppId = sms_sdk_app_id
        # 短信签名内容: 使用 UTF-8 编码，必须填写已审核通过的签名
        # 签名信息可前往 [国内短信](https://console.cloud.tencent.com/smsv2/csms-sign) 或 [国际/港澳台短信](https://console.cloud.tencent.com/smsv2/isms-sign) 的签名管理查看
        req.SignName = sign_name
        # 模板 ID: 必须填写已审核通过的模板 ID
        # 模板 ID 可前往 [国内短信](https://console.cloud.tencent.com/smsv2/csms-template) 或 [国际/港澳台短信](https://console.cloud.tencent.com/smsv2/isms-template) 的正文模板管理查看
        req.TemplateId = template_code
        # 模板参数: 模板参数的个数需要与 TemplateId 对应模板的变量个数保持一致，，若无模板参数，则设置为空
        req.TemplateParamSet = [template_param]
        # 下发手机号码，采用 E.164 标准，+[国家或地区码][手机号]
        # 示例如：+8613711112222， 其中前面有一个+号 ，86为国家码，13711112222为手机号，最多不要超过200个手机号
        req.PhoneNumberSet = [phone_numbers]
        try:
            resp = self.client.SendSms(req)
            # 输出json格式的字符串回包
            res = json.loads(resp.to_json_string(indent=2))
            if res.get('SendStatusSet')[0].get('Code') == "Ok":
                return True, ''
            return False, res.get('SendStatusSet')[0].get('Message')
        except Exception as error:
            # 如有需要，请打印 error
            return False, str(error)