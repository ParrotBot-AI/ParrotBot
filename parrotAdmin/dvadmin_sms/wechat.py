#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import json

from Crypto.Cipher import AES
from django.conf import settings
from redis import Redis
from wechatpy import WeChatClient
from wechatpy.session.redisstorage import RedisStorage

if not hasattr(settings, 'WECHAT_CLIENT_POOL'):
    settings.WECHAT_CLIENT_POOL = {}  # 微信客户端连接池


def get_wechat_pool(app_id, app_secret):
    """
    获取连接池的连接对象
    :param app_id:
    :param app_secret:
    :return:
    """
    if app_id in settings.WECHAT_CLIENT_POOL:
        return settings.WECHAT_CLIENT_POOL[app_id]
    redis_server = f'{settings.REDIS_URL}/{settings.WECHATPY_REDIS_DB or 3}'
    redis_client = Redis.from_url(redis_server)
    session_interface = RedisStorage(redis_client, prefix="wechatpy")
    settings.WECHAT_CLIENT_POOL[app_id] = WeChatClient(app_id, app_secret, session=session_interface)
    return settings.WECHAT_CLIENT_POOL[app_id]


class WXBizDataCrypt:
    """
    微信解密数据
    """

    def __init__(self, app_id, session_key):
        self.app_id = app_id
        self.session_key = session_key

    def decrypt(self, encryptedData, iv):
        # base64 decode
        try:
            session_key = base64.b64decode(self.session_key)
            encrypted_data = base64.b64decode(encryptedData)
            iv = base64.b64decode(iv)
            cipher = AES.new(session_key, AES.MODE_CBC, iv)
            decrypted = json.loads(self._unpad(cipher.decrypt(encrypted_data)))
            if decrypted['watermark']['appid'] != self.app_id:
                raise Exception('Invalid Buffer')
            return decrypted
        except Exception as e:
            print(e)
            return {}

    def _unpad(self, s):
        return s[:-ord(s[len(s) - 1:])]
