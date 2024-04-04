# -*- coding: utf-8 -*-
import time
import uuid
import hashlib
import base64
import requests
import json


class HuaweiCloudSample:
    def __init__(self, access_key_id, access_key_secret):
        '''
        选填,使用无变量模板时请赋空值 TEMPLATE_PARAM = '';
        单变量模板示例:模板内容为"您的验证码是${1}"时,TEMPLATE_PARAM可填写为'["369751"]'
        双变量模板示例:模板内容为"您有${1}件快递请到${2}领取"时,TEMPLATE_PARAM可填写为'["3","人民公园正门"]'
        模板中的每个变量都必须赋值，且取值不能为空
        查看更多模板规范和变量规范:产品介绍>短信模板须知和短信变量须知
        '''
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.sender = "8824032015014"
        # 选填,短信状态报告接收地址,推荐使用域名,为空或者不填表示不接收状态报告
        self.statusCallBack = ""
        # huawei sms 服务url
        self.url = 'https://smsapi.cn-north-4.myhuaweicloud.com:443/sms/batchSendSms/v1'

    def buildWSSEHeader(self, appKey, appSecret) -> str:
        '''
        构造X-WSSE参数值
        @param appKey: string
        @param appSecret: string
        @return: string
        '''
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ')  # Created
        nonce = str(uuid.uuid4()).replace('-', '')  # Nonce
        digest = hashlib.sha256((nonce + now + appSecret).encode()).hexdigest()

        digestBase64 = base64.b64encode(digest.encode()).decode()  # PasswordDigest
        return 'UsernameToken Username="{}",PasswordDigest="{}",Nonce="{}",Created="{}"'.format(appKey, digestBase64,
                                                                                                nonce,
                                                                                                now)

    def send_sms(self, sign_name, template_code, phone_numbers, template_param) -> (bool, str):
        header = {'Authorization': 'WSSE realm="SDP",profile="UsernameToken",type="Appkey"',
                  'X-WSSE': self.buildWSSEHeader(self.access_key_id, self.access_key_secret)}
        # 请求Body
        formData = {
            'from': self.sender,
            'to': phone_numbers,
            'templateId': template_code,
            'templateParas': template_param,
            'statusCallback': self.statusCallBack,
            'signature': sign_name  # 使用国内短信通用模板时,必须填写签名名称
        }

        # 为防止因HTTPS证书认证失败造成API调用失败,需要先忽略证书信任问题
        try:
            resp = requests.post(self.url, data=formData, headers=header, verify=False)
            # 输出json格式的字符串回包
            print(resp.text, 60)  # 打印响应信息
            res = json.loads(resp.to_json_string(indent=2))
            if res.get('SendStatusSet')[0].get('Code') == "Ok":
                return True, ""
            return False, res.get('SendStatusSet')[0].get('Message')
        except Exception as error:
            # 如有需要，请打印 error
            return False, str(resp.text) + ";" + str(error)


if __name__ == '__main__':
    pass
