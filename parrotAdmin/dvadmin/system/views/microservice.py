from dvadmin.system.models import MicroServiceRegister
from dvadmin.system.views.menu import MenuInitSerializer
from dvadmin.utils.json_response import SuccessResponse, DetailResponse
from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.validator import CustomUniqueValidator
from dvadmin.utils.viewset import CustomModelViewSet
from dvadmin.utils.client_info import get_client_ip, get_host
from rest_framework import serializers
from dvadmin.utils.json_response import ErrorResponse, DetailResponse, SuccessResponse
from django.db.models import F, CharField, Value, ExpressionWrapper
from django.db.models.functions import Cast, Concat
from dvadmin.utils.stream_controllers import AdminStream
from rest_framework.decorators import action
from django.core.cache import cache
import random
import jwt
import datetime
import requests
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
import json


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
                    # generate the API_KEY for the microservices
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

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def resource(self, request):
        exam_id = request.data.get("exam_id")
        pattern_id = request.data.get("pattern_id")
        account_id = request.data.get("account_id")

        # whether_zt = request.data.get("is_real_problem") # 目前默认false
        whether_zt = False
        page = request.data.get("page")
        limit = request.data.get("limit")

        if not page:
            page = 1
        else:
            page = int(page)
        if not limit:
            limit = 20
        else:
            limit = int(limit)

        # request send to microservices
        if True:
            # data = dict(micro.data)
            url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/fetch_resource_p/{account_id}/{pattern_id}/"
            r = requests.post(url, json={
                'page': page,
                'limit': limit
            })

            if r.json()['code'] == 10000:
                res_data = r.json()['data']
            else:
                return ErrorResponse(msg="微服务故障")

        # output: resource list with sub question
        return SuccessResponse(data=res_data, msg='获取成功', page=page, limit=limit, total=len(res_data))

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_past_scores/(?P<account_id>\d+)")
    def get_past_scores(self, request, account_id):
        # request send to microservices
        if True:
            try:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/fetch_past_scores/{account_id}/"
                r = requests.get(url)

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                    return DetailResponse(data=res_data, msg='获取成功')
                else:
                    return ErrorResponse(msg=r.json()['msg'])
            except:
                return ErrorResponse(msg="微服务故障")

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def create_mock(self, request):

        question_ids = None
        account_id = request.data.get("account_id")
        if type(request.data.get('question_ids')) == str:
            question_ids = json.loads(request.data.get('question_ids'))
        elif type(request.data.get('question_ids')) == list:
            question_ids = request.data.get('question_ids')

        q_type = request.data.get('q_type')

        # to commend
        user_id = request.data.get("user_id")
        # account_id = 7

        if len(question_ids) < 1:
            return ErrorResponse(msg='至少选择一道题目')

        # request send to microservices
        # input: account_id, question_ids, question_type
        if True:
            try:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/create_sheet"
                r = requests.post(url, json={
                    "account_id": account_id,
                    "question_ids": question_ids,
                    "q_type": q_type
                })

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                    return DetailResponse(data=res_data, msg='获取成功')
                else:
                    return ErrorResponse(msg=r.json()['msg'])
            except:
                return ErrorResponse(msg="微服务故障")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_mock/(?P<sheet_id>\d+)")
    def get_mock(self, request, sheet_id):
        # request send to microservices
        # input: sheet_id
        if True:
            try:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/get_sheet/{sheet_id}/"
                r = requests.get(url)

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                    return DetailResponse(data=res_data, msg='获取成功')
                else:
                    return ErrorResponse(msg=r.json()['msg'])
            except:
                return ErrorResponse(msg="微服务故障")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="answer_status/(?P<sheet_id>\d+)")
    def get_answer_status(self, request, sheet_id):
        if True:
            try:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/get_sheet_status/{sheet_id}/"
                r = requests.get(url)

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                    return DetailResponse(data=res_data, msg='获取成功')
                else:
                    return ErrorResponse(msg=r.json()['msg'])
            except:
                return ErrorResponse(msg="微服务故障")

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def answer_panel(self, request):
        sheet_id = request.data.get('sheet_id')
        question_id = request.data.get('question_id')
        answer = None
        if type(request.data.get('answer')) == str:
            answer = json.loads(request.data.get('answer'))
        elif type(request.data.get('answer')) == list:
            answer = request.data.get('answer')
        duration = request.data.get('duration')
        try:
            # answer = list(answer)
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/update_ans"
                    r = requests.post(url, json={
                        "sheet_id": sheet_id,
                        "question_id": question_id,
                        "answer": answer,
                        "duration": duration
                    })

                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])

                except:
                    return ErrorResponse(msg="微服务故障")
        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated],
            url_path="submit_answers/(?P<sheet_id>\d+)")
    def submit_answers(self, request, sheet_id):
        try:
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/save_answer/{sheet_id}/"
                    r = requests.post(url)

                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg="微服务故障")

        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated], url_path="scoring/(?P<sheet_id>\d+)")
    def scoring(self, request, sheet_id):
        try:
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/scoring/{sheet_id}/"
                    r = requests.post(url)

                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg="微服务故障")

        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated], url_path="get_score/(?P<sheet_id>\d+)")
    def get_score(self, request, sheet_id):
        try:
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/education/get_score/{sheet_id}/"
                    r = requests.get(url)

                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg="微服务故障")

        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_vocabs_statics/(?P<account_id>\d+)")
    def get_vocabs_statics(self, request, account_id):
        # account = 7
        try:
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/get_vocabs_statics/{account_id}/"
                    r = requests.get(url)

                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg="微服务故障")

        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_vocabs_tasks/(?P<account_id>\d+)")
    def get_vocabs_tasks(self, request, account_id):
        try:
            if True:
                try:
                    # data = dict(micro.data)
                    url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/get_today_vocab_task/{account_id}/"
                    r = requests.get(url)

                    if r.json()['code'] == 10000:
                        res_data = r.json()['data']
                        return DetailResponse(data=res_data, msg='OK.')
                    else:
                        return ErrorResponse(msg=r.json()['msg'])
                except:
                    return ErrorResponse(msg="微服务故障")

        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def start_task(self, request):
        task_account_id = request.data.get("task_account_id")
        if True:
            try:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/start_task/"
                r = requests.post(url, json={
                    "task_account_id": task_account_id
                })

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                    return DetailResponse(data=res_data, msg='获取成功')
                else:
                    return ErrorResponse(msg=r.json()['msg'])
            except:
                return ErrorResponse(msg="微服务故障")

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def learning_task(self, request):
        task_account_id = request.data.get("task_account_id")
        payload = request.data.get("payload")
        print(payload, 456)
        if True:
            try:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/learning/learning_task/"
                r = requests.post(url, json={
                    "task_account_id": task_account_id,
                    "payload": payload
                })

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                    return DetailResponse(data=res_data, msg='获取成功')
                else:
                    return ErrorResponse(msg=r.json()['msg'])
            except:
                return ErrorResponse(msg="微服务故障")
