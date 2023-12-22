# -*- coding: utf-8 -*-
import time
import uuid
import hashlib
import base64
import requests  # 需要先使用pip install requests命令安装依赖

# 必填,请参考"开发准备"获取如下数据,替换为实际值
url = 'https://smsapi.cn-north-4.myhuaweicloud.com:443/sms/batchSendSms/v1'  # APP接入地址(在控制台"应用管理"页面获取)+接口访问URI
# 认证用的appKey和appSecret硬编码到代码中或者明文存储都有很大的安全风险，建议在配置文件或者环境变量中密文存放，使用时解密，确保安全；
APP_KEY = "lt7Klp06gISA42uy1ClA5uVI020v"  # APP_Key
APP_SECRET = "prDEfZRWYlupUsBdp9e0ZRQnPIUd"  # APP_Secret
sender = "8823120828568"  # 国内短信签名通道号
TEMPLATE_ID = "6b268b26ac7542fe9906165e95412aa4"  # 模板ID

# 条件必填,国内短信关注,当templateId指定的模板类型为通用模板时生效且必填,必须是已审核通过的,与模板类型一致的签名名称
signature = "华为云短信测试"  # 签名名称

# 必填,全局号码格式(包含国家码),示例:+86151****6789,多个号码之间用英文逗号分隔
receiver = "+8615948356729"  # 短信接收人号码

# 选填,短信状态报告接收地址,推荐使用域名,为空或者不填表示不接收状态报告
statusCallBack = ""

'''
选填,使用无变量模板时请赋空值 TEMPLATE_PARAM = '';
单变量模板示例:模板内容为"您的验证码是${1}"时,TEMPLATE_PARAM可填写为'["369751"]'
双变量模板示例:模板内容为"您有${1}件快递请到${2}领取"时,TEMPLATE_PARAM可填写为'["3","人民公园正门"]'
模板中的每个变量都必须赋值，且取值不能为空
查看更多模板规范和变量规范:产品介绍>短信模板须知和短信变量须知
'''
TEMPLATE_PARAM = '["369751"]'  # 模板变量，此处以单变量验证码短信为例，请客户自行生成6位验证码，并定义为字符串类型，以杜绝首位0丢失的问题（例如：002569变成了2569）。

'''
构造X-WSSE参数值
@param appKey: string
@param appSecret: string
@return: string
'''


def buildWSSEHeader(appKey, appSecret):
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ')  # Created
    nonce = str(uuid.uuid4()).replace('-', '')  # Nonce
    digest = hashlib.sha256((nonce + now + appSecret).encode()).hexdigest()

    digestBase64 = base64.b64encode(digest.encode()).decode()  # PasswordDigest
    return 'UsernameToken Username="{}",PasswordDigest="{}",Nonce="{}",Created="{}"'.format(appKey, digestBase64, nonce,
                                                                                            now)


def main():
    # 请求Headers
    header = {'Authorization': 'WSSE realm="SDP",profile="UsernameToken",type="Appkey"',
              'X-WSSE': buildWSSEHeader(APP_KEY, APP_SECRET)}
    # 请求Body
    formData = {
        'from': sender,
        'to': receiver,
        'templateId': TEMPLATE_ID,
        'templateParas': TEMPLATE_PARAM,
        'statusCallback': statusCallBack,
        'signature': signature #使用国内短信通用模板时,必须填写签名名称
    }
    print(header)

    # 为防止因HTTPS证书认证失败造成API调用失败,需要先忽略证书信任问题
    r = requests.post(url, data=formData, headers=header, verify=False)
    print(r.text)  # 打印响应信息


if __name__ == '__main__':
    main()