import base64
import hashlib
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AbstractBaseUser, update_last_login
from captcha.views import CaptchaStore, captcha_image
from django.contrib import auth
from django.contrib.auth import login
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.status import HTTP_401_UNAUTHORIZED
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import default_user_authentication_rule
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import exceptions, serializers
from django.conf import settings
import json
import re
from application import dispatch
from dvadmin.system.models import Users, Role
from dvadmin.utils.json_response import ErrorResponse, DetailResponse
from dvadmin.utils.request_util import save_login_log
from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.validator import CustomValidationError
from dvadmin_sms.utils import get_sms_code
from dvadmin.system.views.user import UserCreateSerializer
from dvadmin.utils.stream_controllers import AdminStream
import uuid


def generate_uuid_id():
    # 生成一个UUID
    unique_id = uuid.uuid4()
    # 将UUID转换为字符串，并取前10个字符
    short_id = str(unique_id)[:12]
    return short_id


class CaptchaView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        responses={"200": openapi.Response("获取成功")},
        security=[],
        operation_id="captcha-get",
        operation_description="验证码获取",
    )
    def get(self, request):
        data = {}
        if dispatch.get_system_config_values("base.captcha_state"):
            hashkey = CaptchaStore.generate_key()
            id = CaptchaStore.objects.filter(hashkey=hashkey).first().id
            imgage = captcha_image(request, hashkey)
            # 将图片转换为base64
            image_base = base64.b64encode(imgage.content)
            data = {
                "key": id,
                "image_base": "data:image/png;base64," + image_base.decode("utf-8"),
            }
        return DetailResponse(data=data)


class TokenObtainPairWithoutPasswordSerializer(TokenObtainPairSerializer):
    def __init__(self, mobile=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = False
        self.fields['username'].required = False

    def validate(self, attrs):
        if 'mobile' in attrs:
            user = Users.objects.filter(mobile=attrs['mobile']).first()
            attrs.update({'username': user.username})
            attrs.update({'password': user.password})

            # data = super().validate(attrs)
            authenticate_kwargs = {
                self.username_field: attrs[self.username_field],
                "password": attrs["password"],
                "username": attrs["username"],
                "mobile": attrs["mobile"]
            }
            try:
                authenticate_kwargs["request"] = self.context["request"]
            except KeyError:
                pass

            self.user = authenticate(**authenticate_kwargs)

            if not default_user_authentication_rule(self.user):
                raise exceptions.AuthenticationFailed(
                    self.error_messages["no_active_account"],
                    "no_active_account",
                )
            # data = super(TokenObtainPairWithoutPasswordSerializer, self).validate(attrs)
            data = {}

            refresh = self.get_token(self.user)
            data["refresh"] = str(refresh)
            data["access"] = str(refresh.access_token)

            update_last_login(None, self.user)
            return data

        else:
            return super(TokenObtainPairWithoutPasswordSerializer, self).validate(attrs)


class LoginSerializer(TokenObtainPairWithoutPasswordSerializer):
    """
    登录的序列化器:
    重写djangorestframework-simplejwt的序列化器
    """
    captcha = serializers.CharField(
        max_length=6, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = Users
        fields = "__all__"
        # read_only_fields = ["id"]

    default_error_messages = {"no_active_account": _("账号/密码错误")}

    def register_mic(self, u_id):
        import requests
        try:
            # data = dict(micro.data)
            url = f"http://{'127.0.0.1'}:{10981}/v1/api/account/register_user/"
            r = requests.post(url, json={
                "user_id": u_id,
            })

            if r.json()['code'] == 10000:
                res_data = r.json()['data']
                return True, "OK"
            else:
                return False, r.json()['msg']
        except:
            return False, "微服务故障"

        # admin = AdminStream()
        # response = admin.core_register(user_id=str(u_id))
        # return response

    def login(self, attrs, phone=None):
        if phone:
            attrs['mobile'] = phone
            data = super(LoginSerializer, self).validate(attrs)
        else:
            data = super().validate(attrs)

        data["name"] = self.user.name
        data["userId"] = self.user.id
        data["avatar"] = self.user.avatar
        data['user_type'] = self.user.user_type
        dept = getattr(self.user, 'dept', None)
        if dept:
            data['dept_info'] = {
                'dept_id': dept.id,
                'dept_name': dept.name,
            }
        role = getattr(self.user, 'role', None)
        if role:
            data['role_info'] = role.values('id', 'name', 'key')
        request = self.context.get("request")
        request.user = self.user
        # 记录登录日志
        save_login_log(request=request)
        # 是否开启单点登录
        # print(dispatch.get_system_config_values("base.single_login"))
        # if dispatch.get_system_config_values("base.single_login"):
        #     # 将之前登录用户的token加入黑名单
        #     user = Users.objects.filter(id=self.user.id).values('last_token').first()
        #     last_token = user.get('last_token')
        #     if last_token:
        #         try:
        #             token = RefreshToken(last_token)
        #             token.blacklist()
        #         except:
        #             pass
        #     # 将最新的token保存到用户表
        #     Users.objects.filter(id=self.user.id).update(last_token=data.get('refresh'))
        return {"code": 2000, "msg": "请求成功", "data": data}

    def validate(self, attrs):
        cap = False
        if cap:
            captcha = self.initial_data.get("captcha", None)
            if dispatch.get_system_config_values("base.captcha_state"):
                if captcha is None:
                    raise CustomValidationError("图形验证码不能为空")
                self.image_code = CaptchaStore.objects.filter(
                    id=self.initial_data["captchaKey"]
                ).first()
                five_minute_ago = datetime.now() - timedelta(hours=0, minutes=5, seconds=0)
                if self.image_code and five_minute_ago > self.image_code.expiration:
                    self.image_code and self.image_code.delete()
                    raise CustomValidationError("图形验证码过期")
                else:
                    if self.image_code and (
                            self.image_code.response == captcha
                            or self.image_code.challenge == captcha
                    ):
                        self.image_code and self.image_code.delete()
                    else:
                        self.image_code and self.image_code.delete()
                        raise CustomValidationError("图片验证码错误")

        try:
            type = self.initial_data.get("type", None)
            # sms 方式登录
            if type == 'sms':
                phone = self.initial_data.get("mobile", None)
                code = self.initial_data.get("code", None)
                # login_code = code

                login_code = get_sms_code(phone)
                print(login_code, code, 227)
                if login_code:
                    if login_code == code:
                        # to do, find phone number
                        user_phone = Users.objects.filter(mobile=phone).first()
                        if user_phone:
                            return self.login(attrs, phone)
                        else:
                            user_name = generate_uuid_id()
                            user = Users.objects.filter(username=user_name).first()
                            while user:
                                user_name = generate_uuid_id()
                                user = Users.objects.filter(username=user_name).first()

                            user = {
                                "username": user_name,
                                "password": dispatch.get_system_config_values("base.default_password"),
                                "email": "",
                                "mobile": phone,

                                "first_name": "",
                                "last_name": "",
                                "name": "",
                                "avatar": "",

                                "is_staff": False,
                                "user_type": 1,
                                "creator": 1,
                                "is_active": True
                            }

                            serializer = UserCreateSerializer(data=user)
                            try:
                                serializer.is_valid(raise_exception=True)
                            except Exception as Error:
                                raise CustomValidationError(Error)
                            serializer.save()
                            user = Users.objects.filter(username=user_name).first()

                            # 注册该用户到用户表
                            if user:
                                try:
                                    role = Role.objects.get(name='用户')
                                    user.role.add(role)
                                    user.save()
                                except ObjectDoesNotExist:
                                    print("Role does not exist.")

                            # 注册用户到 microservices, 支持异步
                            res, data = self.register_mic(user.id)
                            if res:
                                # 登录
                                return self.login(attrs, phone)
                            else:
                                return ErrorResponse(msg=data)
                    else:
                        raise CustomValidationError("验证码不匹配, 请重新发送")
                else:
                    raise CustomValidationError("验证码未找到或已过期，请重新发送")
            elif type == 'account':
                pattern = r'^\d{11}$'
                user = None
                if re.match(pattern, attrs['username']):
                    user = Users.objects.filter(mobile=attrs['username']).first()
                else:
                    user = Users.objects.filter(username=attrs['username']).first()

                if user:
                    attrs.update({'username': user.username})
                    return self.login(attrs)

                else:
                    user = {
                        "username": attrs["username"],
                        "password": attrs["password"],
                        "email": "",
                        "mobile": "",

                        "first_name": "",
                        "last_name": "",
                        "name": "",
                        "avatar": "",

                        "is_staff": False,
                        "user_type": 1,
                        "creator": 1,
                        "is_active": True
                    }

                    serializer = UserCreateSerializer(data=user)
                    try:
                        serializer.is_valid(raise_exception=True)
                    except Exception as Error:
                        raise CustomValidationError(Error)
                    serializer.save()
                    user = Users.objects.filter(username=attrs["username"]).first()

                    if user:
                        try:
                            role = Role.objects.get(name='用户')
                            user.role.add(role)
                            user.save()
                        except ObjectDoesNotExist:
                            print("Role does not exist.")

                    # 注册用户到 microservices, 支持异步
                    res, data = self.register_mic(user.id)
                    if res:
                        # 登录
                        return self.login(attrs)
                    else:
                        return ErrorResponse(msg=data)
            else:
                user = Users.objects.filter(username=attrs['username']).first()
                if user:
                    return self.login(attrs)
        except:
            # username = self.initial_data.get("username", None)
            # user = Users.objects.filter(username=username).first()
            # if user.username == 'test12142':
            #     attrs.update({'password': 'test12138'})
            # if user:
            #     return self.login(attrs)
            raise CustomValidationError("登录认证失败")


class CustomTokenRefreshView(TokenRefreshView):
    """
    自定义token刷新
    """

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        try:
            token = RefreshToken(refresh_token)
            data = {
                "access": str(token.access_token),
                "refresh": str(token)
            }
        except:
            return ErrorResponse(status=HTTP_401_UNAUTHORIZED)
        return DetailResponse(data=data)


class LoginView(TokenObtainPairView):
    """
    登录接口
    """
    serializer_class = LoginSerializer
    permission_classes = []


class LoginTokenSerializer(TokenObtainPairSerializer):
    """
    登录的序列化器:
    """

    class Meta:
        model = Users
        fields = "__all__"
        read_only_fields = ["id"]

    default_error_messages = {"no_active_account": _("账号/密码不正确")}

    def validate(self, attrs):
        if not getattr(settings, "LOGIN_NO_CAPTCHA_AUTH", False):
            return {"code": 4000, "msg": "该接口暂未开通!", "data": None}
        data = super().validate(attrs)
        data["name"] = self.user.name
        data["userId"] = self.user.id
        return {"code": 2000, "msg": "请求成功", "data": data}


class LoginTokenView(TokenObtainPairView):
    """
    登录获取token接口
    """

    serializer_class = LoginTokenSerializer
    permission_classes = []


class LogoutView(APIView):
    def post(self, request):
        Users.objects.filter(id=self.request.user.id).update(last_token=None)
        return DetailResponse(msg="退出登录成功")


class ApiLoginSerializer(CustomModelSerializer):
    """接口文档登录-序列化器"""

    username = serializers.CharField()
    password = serializers.CharField()

    class Meta:
        model = Users
        fields = ["username", "password"]


class ApiLogin(APIView):
    """接口文档的登录接口"""

    serializer_class = ApiLoginSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user_obj = auth.authenticate(
            request,
            username=username,
            password=hashlib.md5(password.encode(encoding="UTF-8")).hexdigest(),
        )
        if user_obj:
            login(request, user_obj)
            return redirect("/")
        else:
            return ErrorResponse(msg="账号/密码错误")
