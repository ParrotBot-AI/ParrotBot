from dvadmin.system.models import MicroServiceRegister
from dvadmin.system.views.menu import MenuInitSerializer
from dvadmin.utils.json_response import SuccessResponse, DetailResponse
from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.validator import CustomUniqueValidator
from dvadmin.utils.viewset import CustomModelViewSet
from dvadmin.utils.client_info import get_client_ip, get_host
from rest_framework import serializers
from dvadmin.utils.json_response import ErrorResponse, DetailResponse
from django.db.models import F, CharField, Value, ExpressionWrapper
from django.db.models.functions import Cast, Concat
from dvadmin.utils.stream_controllers import AdminStream
from rest_framework.decorators import action
from django.core.cache import cache
import random
import jwt
import datetime


class MicroServiceInitRegisterSerializer(CustomModelSerializer):
    """
    初始化微服务-序列化器
    """

    class Meta:
        model = MicroServiceRegister
        fields = "__all__"
        read_only_fields = ["id"]


class MicroServiceRegisterSerializer(CustomModelSerializer):
    """
    微服务-序列化器
    """

    class Meta:
        model = MicroServiceRegister
        fields = "__all__"
        read_only_fields = ["id", "port", "host"]


class MicroServiceCreateUpdateSerializer(CustomModelSerializer):
    """
    微服务-管理 创建/更新时的列化器
    """

    class Meta:
        model = MicroServiceRegister
        fields = "__all__"
        read_only_fields = ["id"]


class MicroServiceRegisterViewSet(CustomModelViewSet):
    """
    微服务管理接口
    list:查询
    create:新增
    update:修改
    retrieve:单例
    destroy:删除
    """

    queryset = MicroServiceRegister.objects.all()
    serializer_class = MicroServiceRegisterSerializer
    create_serializer_class = MicroServiceCreateUpdateSerializer
    update_serializer_class = MicroServiceCreateUpdateSerializer
    extra_filter_backends = []

    @action(methods=["GET"], detail=False, permission_classes=[])
    def test_streaming(self, request):
        """
        测试streaming
        """
        AdminStream.admin_action("account_register", test=str(True), core=str(True))
        return DetailResponse(msg='OK', data={})

    @action(methods=["GET"], detail=False, permission_classes=[])
    def get_service_permission_code(self, request):
        """
        获取请求的微服务权限
        """
        code = random.randint(100000, 999999)
        host = get_host(request)
        name = request.data.name
        cache.set(f"service_code_{host}_{name}", code, 300)  # 5分钟有效期
        return DetailResponse(msg='OK', data={'code': code})

    @action(methods=["POST"], detail=False, permission_classes=[])
    def service_register(self, request):
        """
        注册微服务
        """
        data = request.data
        if data.code:
            code = data.code
            host = data.host
            name = data.name
            code_s = cache.get(f"service_code_{host}_{name}")
            if code_s:
                if code == code_s:
                    # generate the API_KEY for the microservice
                    secret_key = locals().get('m_secret_key', "")

                    payload = {
                        "user_id": "12345",
                        "name": name,
                        "host": host,
                        "port": data.port,
                        "exp": datetime.datetime.utcnow()
                    }
                    encoded_jwt = jwt.encode(payload, secret_key, algorithm="HS256")

                    service = {
                        "name": name,
                        "host": host,
                        "port": data.port,
                        "method": data.method,
                        "heartBeatApi": data.heart_beat_api,
                        "frequency": 60 * 60,
                        "status": 1,
                        "API_Key": encoded_jwt,
                    }
                    try:
                        m_serializer = MicroServiceRegisterSerializer(data=service, request=request)
                        m_serializer.is_valid(raise_exception=True)
                        # serializer.save()
                        self.perform_create(m_serializer)
                        # to do: 注册 heartbeat task

                        # 注册 menu 与 menu button
                        menu = data.menu
                        model = MenuInitSerializer.Meta.model
                        for data in menu:
                            filter_data = {}
                            unique_fields = ['name', 'web_path', 'component', 'component_name']
                            # 配置过滤条件,如果有唯一标识字段则使用唯一标识字段，否则使用全部字段
                            if unique_fields:
                                for field in unique_fields:
                                    if field in data:
                                        filter_data[field] = data[field]
                            else:
                                for key, value in data.items():
                                    if isinstance(value, list) or value == None or value == '':
                                        continue
                                    filter_data[key] = value
                            instance = model.objects.filter(**filter_data).first()
                            data["reset"] = self.reset
                            serializer = MenuInitSerializer(instance, data=data, request=self.request)
                            serializer.is_valid(raise_exception=True)
                            serializer.save()
                        return DetailResponse(data=m_serializer.data, msg="新增成功")
                    except:
                        return ErrorResponse(msg="微服务注册失败")
                else:
                    return ErrorResponse(msg="微服务权限不匹配")
            else:
                return ErrorResponse(msg="微服务权限已过期")
        else:
            return ErrorResponse(msg="无效微服务权限")
