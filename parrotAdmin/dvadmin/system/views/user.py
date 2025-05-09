import hashlib
import json

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.hashers import make_password, check_password
from django_restql.fields import DynamicSerializerMethodField
from django.contrib.auth.password_validation import (
    validate_password,
    password_changed,
)
from rest_framework import serializers
from rest_framework.decorators import action, permission_classes, api_view
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.db import connection
from application import dispatch
from dvadmin.system.models import Users, Role, Dept
from dvadmin.system.views.role import RoleSerializer
from dvadmin.utils.json_response import ErrorResponse, DetailResponse
from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.validator import CustomUniqueValidator
from dvadmin.utils.viewset import CustomModelViewSet
from dvadmin.utils.image_tools import save_new_avatar, separate_avatar_field
from dvadmin_sms.utils import get_sms_code
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from dvadmin.utils.request_util import save_login_log
from dvadmin.utils.validator import CustomValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import requests
import logging

logger = logging.getLogger(__name__)


def recursion(instance, parent, result):
    new_instance = getattr(instance, parent, None)
    res = []
    data = getattr(instance, result, None)
    if data:
        res.append(data)
    if new_instance:
        array = recursion(new_instance, parent, result)
        res += (array)
    return res


class UserInterfaceSerializer(CustomModelSerializer):
    class Meta:
        model = Users
        read_only_fields = ["id"]
        fields = ["username", "email", 'mobile', 'avatar', "name", 'gender',
                  'first_name', 'last_name', 'email']


class UserSerializer(CustomModelSerializer):
    """
    用户管理-序列化器
    """
    dept_name = serializers.CharField(source='dept.name', read_only=True)
    role_info = DynamicSerializerMethodField()

    class Meta:
        model = Users
        read_only_fields = ["id"]
        exclude = ["password"]
        extra_kwargs = {
            "post": {"required": False},
        }

    def get_role_info(self, instance, parsed_query):
        roles = instance.role.all()
        # You can do what ever you want in here
        # `parsed_query` param is passed to BookSerializer to allow further querying
        serializer = RoleSerializer(
            roles,
            many=True,
            parsed_query=parsed_query
        )
        return serializer.data


class UsersInitSerializer(CustomModelSerializer):
    """
    初始化获取数信息(用于生成初始化json文件)
    """

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        role_key = self.initial_data.get('role_key', [])
        role_ids = Role.objects.filter(key__in=role_key).values_list('id', flat=True)
        instance.role.set(role_ids)
        dept_key = self.initial_data.get('dept_key', None)
        dept_id = Dept.objects.filter(key=dept_key).first()
        instance.dept = dept_id
        instance.save()
        return instance

    class Meta:
        model = Users
        fields = ["username", "email", 'mobile', 'avatar', "name", 'gender', 'user_type', "dept", 'user_type',
                  'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'creator', 'dept_belong_id',
                  'password', 'last_login', 'is_superuser']
        read_only_fields = ['id']
        extra_kwargs = {
            'creator': {'write_only': True},
            'dept_belong_id': {'write_only': True}
        }


class UserCreateSerializer(CustomModelSerializer):
    """
    用户新增-序列化器
    """

    username = serializers.CharField(
        max_length=50,
        validators=[
            CustomUniqueValidator(queryset=Users.objects.all(), message="账号必须唯一")
        ],
    )
    mobile = serializers.CharField(
        max_length=50,
        validators=[
            CustomUniqueValidator(queryset=Users.objects.all(), message="手机号必须唯一")
        ],
        allow_blank=True
    )
    password = serializers.CharField(
        required=False,
    )

    def validate_password(self, value):
        """
        对密码进行验证
        """
        password = self.initial_data.get("password")
        if password:
            return make_password(value)
        return value

    def save(self, **kwargs):
        data = super().save(**kwargs)
        data.dept_belong_id = data.dept_id
        data.save()
        data.post.set(self.initial_data.get("post", []))
        return data

    class Meta:
        model = Users
        fields = "__all__"
        read_only_fields = ["id"]
        extra_kwargs = {
            "post": {"required": False},
        }


class UserUpdateSerializer(CustomModelSerializer):
    """
    用户修改-序列化器
    """

    username = serializers.CharField(
        max_length=50,
        validators=[
            CustomUniqueValidator(queryset=Users.objects.all(), message="账号必须唯一")
        ],
    )
    # password = serializers.CharField(required=False, allow_blank=True)
    mobile = serializers.CharField(
        max_length=50,
        validators=[
            CustomUniqueValidator(queryset=Users.objects.all(), message="手机号必须唯一")
        ],
        allow_blank=True
    )

    def save(self, **kwargs):
        data = super().save(**kwargs)
        data.dept_belong_id = data.dept_id
        data.save()
        data.post.set(self.initial_data.get("post", []))
        return data

    class Meta:
        model = Users
        read_only_fields = ["id", "password"]
        fields = "__all__"
        extra_kwargs = {
            "post": {"required": False, "read_only": True},
        }


class UserInfoUpdateSerializer(CustomModelSerializer):
    """
    用户修改-序列化器
    """
    mobile = serializers.CharField(
        max_length=50,
        validators=[
            CustomUniqueValidator(queryset=Users.objects.all(), message="手机号必须唯一")
        ],
        allow_blank=True
    )

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    class Meta:
        model = Users
        fields = ['email', 'avatar', 'name', 'gender', 'first_name', 'last_name']
        extra_kwargs = {
            "post": {"required": False, "read_only": True},
        }


class ExportUserProfileSerializer(CustomModelSerializer):
    """
    用户导出 序列化器
    """

    last_login = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", required=False, read_only=True
    )
    is_active = serializers.SerializerMethodField(read_only=True)
    dept_name = serializers.CharField(source="dept.name", default="")
    dept_owner = serializers.CharField(source="dept.owner", default="")
    gender = serializers.CharField(source="get_gender_display", read_only=True)

    def get_is_active(self, instance):
        return "启用" if instance.is_active else "停用"

    class Meta:
        model = Users
        fields = (
            "username",
            "name",
            "email",
            "mobile",
            "gender",
            "is_active",
            "last_login",
            "dept_name",
            "dept_owner",
        )


class UserProfileImportSerializer(CustomModelSerializer):
    password = serializers.CharField(required=True, max_length=50, error_messages={"required": "登录密码不能为空"})

    def save(self, **kwargs):
        data = super().save(**kwargs)
        password = hashlib.new(
            "md5", str(self.initial_data.get("password", "admin123456")).encode(encoding="UTF-8")
        ).hexdigest()
        data.set_password(password)
        data.save()
        return data

    class Meta:
        model = Users
        exclude = (
            "post",
            "user_permissions",
            "groups",
            "is_superuser",
            "date_joined",
        )


class UserViewSet(CustomModelViewSet):
    """
    用户接口
    list:查询
    create:新增
    update:修改
    retrieve:单例
    destroy:删除
    """
    queryset = Users.objects.exclude(is_superuser=1).all()
    serializer_class = UserSerializer
    create_serializer_class = UserCreateSerializer
    update_serializer_class = UserUpdateSerializer
    filter_fields = ["^name", "~username", "^mobile", "is_active", "dept", "user_type", "$dept__name"]

    search_fields = ["username", "name", "gender", "dept__name", "role__name"]
    # 导出
    export_field_label = {
        "username": "用户账号",
        "name": "用户名称",
        "email": "用户邮箱",
        "mobile": "手机号码",
        "gender": "用户性别",
        "is_active": "帐号状态",
        "user_type": "是否为前台用户",
        "last_login": "最后登录时间",
        # "dept_name": "部门名称",
        # "dept_owner": "部门负责人",
    }
    export_serializer_class = ExportUserProfileSerializer
    # 导入
    import_serializer_class = UserProfileImportSerializer
    import_field_dict = {
        "username": "登录账号",
        "name": "用户名称",
        "email": "用户邮箱",
        "mobile": "手机号码",
        "gender": {
            "title": "用户性别",
            "choices": {
                "data": {"未知": 2, "男": 1, "女": 0},
            }
        },
        "is_active": {
            "title": "帐号状态",
            "choices": {
                "data": {"启用": True, "禁用": False},
            }
        },
        "password": "登录密码",
        "user_type": "是否为前台用户",
        "dept": {"title": "部门", "choices": {"queryset": Dept.objects.filter(status=True), "values_name": "name"}},
        "role": {"title": "角色", "choices": {"queryset": Role.objects.filter(status=True), "values_name": "name"}},
    }

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_user_accounts/(?P<userID>\d+)")
    def get_user_accounts(self, request, userID):
        if userID:
            exam_id = request.data.get('exam_id')

            # request user statis from another app
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/account/get_user_accounts/{userID}/"
                    r = requests.post(url, json={
                        "exam_id": exam_id
                    })
                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg='服务器故障')
            return DetailResponse(data=res_data, msg="获取成功")
        else:
            ErrorResponse(msg="请传入正确id值")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_account_checkin/(?P<account_id>\d+)")
    def get_account_checkin(self, request, account_id):
        if account_id:
            # request user statis from another app
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/get_checkin_info/{account_id}/"
                    r = requests.get(url)
                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg='服务器故障')
        else:
            ErrorResponse(msg="请传入正确account_id值")

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated],
            url_path="update_account_checkin/(?P<account_id>\d+)")
    def update_account_checkin(self, request, account_id):
        if account_id:
            time_length = request.data.get("time_length")
            # request user statis from another app
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/add_pulse_time/{account_id}/"
                    r = requests.post(url, json={
                        "time_length": time_length
                    })
                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg='服务器故障')
        else:
            ErrorResponse(msg="请传入正确account_id值")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated], url_path="get_user/(?P<userID>\d+)")
    def get_user_id(self, request, userID):
        if userID:
            queryset = self.queryset.filter(id=userID).first()
            serializer = UserInterfaceSerializer(queryset, many=False, request=request)
            data = serializer.data

            # request user statis from another app
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/account/get_user_info/{userID}/"
                    r = requests.get(url)
                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg='服务器故障')

            for key in res_data.keys():
                data[key] = res_data[key]

            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/get_today_tasks/{userID}/"
                    r = requests.get(url)
                    if r.json()['code'] == 10000:
                        _res_data = r.json()['data']
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg='服务器故障')

            data['tdy'] = [x for x in _res_data if x['level'] == 0]
            data['wk'] = [x for x in _res_data if x['level'] == 1]
            return DetailResponse(data=data, msg="获取成功")
        else:
            ErrorResponse(msg="请传入正确id值")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated])
    def user_info(self, request):
        """获取当前用户信息"""
        user = request.user
        result = {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "mobile": user.mobile,
            "user_type": user.user_type,
            "gender": user.gender,
            "email": user.email,
            "avatar": user.avatar,
            "dept": user.dept_id,
            "is_superuser": user.is_superuser,
            "role": user.role.values_list('id', flat=True),
        }
        if hasattr(connection, 'tenant'):
            result['tenant_id'] = connection.tenant and connection.tenant.id
            result['tenant_name'] = connection.tenant and connection.tenant.name
        dept = getattr(user, 'dept', None)
        if dept:
            result['dept_info'] = {
                'dept_id': dept.id,
                'dept_name': dept.name
            }
        role = getattr(user, 'role', None)
        if role:
            result['role_info'] = role.values('id', 'name', 'key')
        return DetailResponse(data=result, msg="获取成功")

    @action(methods=["PUT"], detail=False, permission_classes=[IsAuthenticated])
    def update_user_info(self, request):
        """修改当前用户信息"""
        serializer = UserInfoUpdateSerializer(request.user, data=request.data, request=request, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return DetailResponse(data=None, msg="修改成功")

    @action(methods=["PUT"], detail=True, permission_classes=[IsAuthenticated])
    def change_password(self, request, *args, **kwargs):
        """密码修改"""
        data = request.data
        phone = data.get("phone")
        code = data.get("code")

        old_pwd = data.get("oldPassword")
        new_pwd = data.get("newPassword")
        new_pwd2 = data.get("newPassword2")
        # 手机修改
        if phone:
            login_code = get_sms_code(phone)
            if login_code:
                if str(login_code) == str(code):
                    request.user.password = make_password(new_pwd)
                    request.user.save()
                    return DetailResponse(data=None, msg="修改成功")
            return ErrorResponse(msg="验证码错误")
        else:
            if old_pwd is None or new_pwd is None or new_pwd2 is None:
                return ErrorResponse(msg="参数不能为空")
            if new_pwd != new_pwd2:
                return ErrorResponse(msg="两次密码不匹配")

            verify_password = check_password(old_pwd, self.request.user.password)
            if not verify_password:
                verify_password = check_password(hashlib.md5(old_pwd.encode(encoding='UTF-8')).hexdigest(),
                                                 self.request.user.password)
            if verify_password:
                request.user.password = make_password(new_pwd)
                request.user.save()
                return DetailResponse(data=None, msg="修改成功")
            else:
                return ErrorResponse(msg="旧密码不正确")

    @action(methods=["PUT"], detail=True, permission_classes=[IsAuthenticated])
    def reset_to_default_password(self, request, *args, **kwargs):
        """恢复默认密码"""
        instance = Users.objects.filter(id=kwargs.get("pk")).first()
        if instance:
            instance.set_password(dispatch.get_system_config_values("base.default_password"))
            instance.save()
            return DetailResponse(data=None, msg="密码重置成功")
        else:
            return ErrorResponse(msg="未获取到用户")

    @action(methods=["PUT"], detail=True)
    def reset_password(self, request, pk):
        """
        密码重置
        """
        data = request.data

        # 验证sms/email
        choice = data.get("type")
        if choice == 'sms':
            # sms check #
            code = data.get("code")
            phone = data.get("phone")
            valid_code = get_sms_code(phone)
            if valid_code:
                if not code == valid_code:
                    pass
                else:
                    return ErrorResponse(msg="验证码错误")
            else:
                return ErrorResponse(msg="验证码已过期，请重新请求")

        # email check
        elif choice == 'email':
            return ErrorResponse(msg="该功能暂未开通")

        instance = Users.objects.filter(id=pk).first()
        new_pwd = data.get("newPassword")
        new_pwd2 = data.get("newPassword2")
        if instance:
            if new_pwd != new_pwd2:
                return ErrorResponse(msg="两次密码不匹配")
            else:
                instance.password = make_password(new_pwd)
                instance.save()
                return DetailResponse(data=None, msg="修改成功")
        else:
            return ErrorResponse(msg="未获取到用户")

    # views for user
