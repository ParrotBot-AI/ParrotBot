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
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated, AllowAny


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
        # whether_zt = request.data.get("is_real_problem") # 目前默认false
        whether_zt = False
        page = request.data.get("page")
        limit = request.data.get("limit")

        if not page:
            page = 1
        else:
            page = int(page)
        if not limit:
            limit = 10
        else:
            limit = int(limit)

        # request send to microservices
        # input: exam_id, pattern_id, whether_zt
        # output: resource list with sub question

        resource = [
            {
                "resource_id": 1,
                "resource_parent_name": "TPO 1",
                "resource_name": "TPO 1-阅读",
                "sections":
                    [
                        {
                            "section_id": 1,
                            "section_name": "第一篇阅读",
                            "questions": [
                                {
                                    "question_id": 1,
                                    "question_name": "How a visual artist redefines success in graphic design",
                                    "question_count": 10,
                                    "order": 1,
                                    "remark": "Passage 1",
                                    "last_record": 6
                                },
                                {
                                    "question_id": 2,
                                    "question_name": "Travelling as a way of self-discovery and progress",
                                    "question_count": 10,
                                    "order": 2,
                                    "remark": "Passage 1",
                                    "last_record": 6
                                },
                                {
                                    "question_id": 3,
                                    "question_name": "Start a blog to reach your creative peak",
                                    "question_count": 10,
                                    "order": 3,
                                    "remark": "Passage 1",
                                    "last_record": 6
                                },
                            ]
                        }
                    ]

            },
            {
                "resource_id": 2,
                "resource_parent_name": "TPO 2",
                "resource_name": "TPO 2-阅读",
                "sections":
                    [
                        {
                            "section_id": 2,
                            "section_name": "第一篇阅读",
                            "questions": [
                                {
                                    "question_id": 11,
                                    "question_name": "How a visual artist redefines success in graphic design",
                                    "question_count": 10,
                                    "order": 1,
                                    "remark": "Passage 1",
                                    "last_record": 6
                                },
                                {
                                    "question_id": 12,
                                    "question_name": "Travelling as a way of self-discovery and progress",
                                    "question_count": 10,
                                    "order": 2,
                                    "remark": "Passage 1",
                                    "last_record": 6
                                },
                                {
                                    "question_id": 13,
                                    "question_name": "Start a blog to reach your creative peak",
                                    "question_count": 10,
                                    "order": 3,
                                    "remark": "Passage 1",
                                    "last_record": 6
                                },
                            ]
                        }
                    ]
            },

        ]
        return SuccessResponse(data=resource, msg='获取成功', page=page, limit=limit, total=len(resource))

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def create_mock(self, request):
        user_id = request.data.get("user_id")
        question_ids = request.data.get("question_ids")
        if question_ids:
            question_ids = list(question_ids)
            if len(question_ids) < 1:
                return ErrorResponse(msg='至少选择一道题目')

        # whether_zt = request.data.get("is_real_problem") # 目前默认false

        # request send to microservices
        # input: user_id, question_ids
        # output: resource list with sub questions

        mock = {
            'practice_id': 1,
            'is_time': True,
            'is_check_answer': False,
            'time_remain': 1800,  # 秒
            'questions': [
                {
                    "question_id": 1,
                    "question_title": "Portraits as Art",
                    "questions_content": "Darwin's theory is that 'selective breeding' occurs in nature as 'natural selection' is the engine behind evolution. $$ Thus, the theory provides an excellent basis for understanding how organisms change over time. $$ Nevertheless, it is just a theory and elusively difficult to prove. One of the major holes in Darwin's theory revolves around “irreducibly complex systems.” An irreducibly complex system is known as a system where many different parts must all operate together. As a result, in the absence of one, the system as a whole collapses. Consequently, as modern technology improves, science can identify these “irreducibly complex systems” even at microscopic levels. These complex systems, if so inter-reliant, would be resistant to Darwin's supposition of how evolution occurs. As Darwin himself admitted, “To suppose that the eye with all its inimitable contrivance for adjusting the focus for different distances, for admitting different amounts of light, and for the correction of spherical and chromatic aberration, could have been formed by natural selection, seems, I free confess, absurd in the highest degree.\nIn conclusion, “On the Origin of Species” is known as one of the most consequential books ever published. Darwin's Theory of Evolution remains, to this day, a lightning rod for controversy. The theory can be observed repeatedly, but never proven, and there are a plethora of instances that cast doubt on the processes of natural selection and evolution. Darwin's conclusions were a result of keen observation and training as a naturalist. Despite the controversy that swirls around his theory, Darwin remains one of the most influential scientists and naturalists ever born due to his Theory of Evolution.",
                    "keywords": "$$",
                    "question_depth": 0,
                    "question_count": 10,
                    "children": [
                        {
                            "question_id": 2,
                            "stem": "The word “engage” in the passage is closest in meaning to",
                            "keywords": "engage",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 1,
                            "choice": ["construct", "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_sc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "restriction_count": 1,
                            "answer": [0, 0, 0, 0],
                        },
                        {
                            "question_id": 3,
                            "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                            "keywords": "",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 2,
                            "choice": [
                                "Portraits representing faces are more true to life than portraits that portray a whole figure.",
                                "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_mc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 1, 0],
                            "restriction_count": 2,
                            "answer": [0, 0, 0, 0],
                            "restriction": {
                                1: 0,
                                0: 0
                            }
                        },
                        {
                            "question_id": 4,
                            "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage. \n In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "keywords": "In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 3,
                            "choice": ["", "", "", ""],
                            "question_type": "TR_fill_sentence",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 5,
                            "stem": "Portraiture as an art form is more complex than is suggested by its definition.",
                            "keywords": "",
                            "paragraph": None,
                            "question_depth": 1,
                            "order": 4,
                            "choice": [
                                "The definitions of portrait art in the dictionary have regularly transformed throughout the years to reflect shifting attitudes regarding the genre.",
                                "Portraits generally mirror the conventions of the time rather than the unique qualities of the individual.",
                                "Portrait art should be considered as a distinct artistic genre due to its intense occupation with the subject and the way in which it was produced.",
                                "Throughout history, the majority of professional artists avoided portrait art since they regarded it as a mechanical art form, and not as fine art.",
                                'Beginning in the Renaissance and continuing into the start of the nineteenth century, portrait art was idealized to a greater degree than it is in today.',
                                "Portrait art was at times viewed in a negative light since it was considered as simple copying void of artistic innovation."],
                            "question_type": "TR_last_mc",
                            "choice_label": ["A", "B", "C", "D", "E", "F"],
                            "answer_weight": [1, 0, 1, 0, 1, 0],
                            "answer": [0, 0, 0, 0, 0, 0],
                            "restriction_count": 3,
                            "restriction": {
                                2: 1,
                                1: 0,
                                0: 0
                            }
                        },

                    ]
                },
                {
                    "question_id": 6,
                    "question_title": "Portraits as Art",
                    "questions_content": "Darwin's theory is that 'selective breeding' occurs in nature as 'natural selection' is the engine behind evolution. $$ Thus, the theory provides an excellent basis for understanding how organisms change over time. $$ Nevertheless, it is just a theory and elusively difficult to prove. One of the major holes in Darwin's theory revolves around “irreducibly complex systems.” An irreducibly complex system is known as a system where many different parts must all operate together. As a result, in the absence of one, the system as a whole collapses. Consequently, as modern technology improves, science can identify these “irreducibly complex systems” even at microscopic levels. These complex systems, if so inter-reliant, would be resistant to Darwin's supposition of how evolution occurs. As Darwin himself admitted, “To suppose that the eye with all its inimitable contrivance for adjusting the focus for different distances, for admitting different amounts of light, and for the correction of spherical and chromatic aberration, could have been formed by natural selection, seems, I free confess, absurd in the highest degree.\nIn conclusion, “On the Origin of Species” is known as one of the most consequential books ever published. Darwin's Theory of Evolution remains, to this day, a lightning rod for controversy. The theory can be observed repeatedly, but never proven, and there are a plethora of instances that cast doubt on the processes of natural selection and evolution. Darwin's conclusions were a result of keen observation and training as a naturalist. Despite the controversy that swirls around his theory, Darwin remains one of the most influential scientists and naturalists ever born due to his Theory of Evolution.",
                    "keywords": "$$",
                    "question_depth": 0,
                    "question_count": 10,
                    "children": [
                        {
                            "question_id": 7,
                            "stem": "The word “engage” in the passage is closest in meaning to",
                            "keywords": "engage",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 1,
                            "choice": ["construct", "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_sc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 8,
                            "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                            "keywords": "",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 2,
                            "choice": [
                                "Portraits representing faces are more true to life than portraits that portray a whole figure.",
                                "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_mc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 1, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 2,
                            "restriction": {
                                1: 0,
                                0: 0
                            }
                        },
                        {
                            "question_id": 9,
                            "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage. \n In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "keywords": "In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 3,
                            "choice": ["", "", "", ""],
                            "question_type": "TR_fill_sentence",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 10,
                            "stem": "Portraiture as an art form is more complex than is suggested by its definition.",
                            "keywords": "",
                            "paragraph": None,
                            "question_depth": 1,
                            "order": 4,
                            "choice": [
                                "The definitions of portrait art in the dictionary have regularly transformed throughout the years to reflect shifting attitudes regarding the genre.",
                                "Portraits generally mirror the conventions of the time rather than the unique qualities of the individual.",
                                "Portrait art should be considered as a distinct artistic genre due to its intense occupation with the subject and the way in which it was produced.",
                                "Throughout history, the majority of professional artists avoided portrait art since they regarded it as a mechanical art form, and not as fine art.",
                                'Beginning in the Renaissance and continuing into the start of the nineteenth century, portrait art was idealized to a greater degree than it is in today.',
                                "Portrait art was at times viewed in a negative light since it was considered as simple copying void of artistic innovation."],
                            "question_type": "TR_last_mc",
                            "choice_label": ["A", "B", "C", "D", "E", "F"],
                            "answer_weight": [1, 0, 1, 0, 1, 0],
                            "answer": [0, 0, 0, 0, 0, 0],
                            "restriction_count": 3,
                            "restriction": {
                                2: 1,
                                1: 0,
                                0: 0
                            }
                        },

                    ]
                },
                {
                    "question_id": 11,
                    "question_title": "Portraits as Art",
                    "questions_content": "Darwin's theory is that 'selective breeding' occurs in nature as 'natural selection' is the engine behind evolution. $$ Thus, the theory provides an excellent basis for understanding how organisms change over time. $$ Nevertheless, it is just a theory and elusively difficult to prove. One of the major holes in Darwin's theory revolves around “irreducibly complex systems.” An irreducibly complex system is known as a system where many different parts must all operate together. As a result, in the absence of one, the system as a whole collapses. Consequently, as modern technology improves, science can identify these “irreducibly complex systems” even at microscopic levels. These complex systems, if so inter-reliant, would be resistant to Darwin's supposition of how evolution occurs. As Darwin himself admitted, “To suppose that the eye with all its inimitable contrivance for adjusting the focus for different distances, for admitting different amounts of light, and for the correction of spherical and chromatic aberration, could have been formed by natural selection, seems, I free confess, absurd in the highest degree.\nIn conclusion, “On the Origin of Species” is known as one of the most consequential books ever published. Darwin's Theory of Evolution remains, to this day, a lightning rod for controversy. The theory can be observed repeatedly, but never proven, and there are a plethora of instances that cast doubt on the processes of natural selection and evolution. Darwin's conclusions were a result of keen observation and training as a naturalist. Despite the controversy that swirls around his theory, Darwin remains one of the most influential scientists and naturalists ever born due to his Theory of Evolution.",
                    "keywords": "$$",
                    "question_depth": 0,
                    "question_count": 10,
                    "children": [
                        {
                            "question_id": 12,
                            "stem": "The word “engage” in the passage is closest in meaning to",
                            "keywords": "engage",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 1,
                            "choice": ["construct", "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_sc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 13,
                            "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                            "keywords": "",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 2,
                            "choice": [
                                "Portraits representing faces are more true to life than portraits that portray a whole figure.",
                                "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_mc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 1, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 2,
                            "restriction": {
                                1: 0,
                                0: 0
                            }
                        },
                        {
                            "question_id": 14,
                            "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage. \n In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "keywords": "In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 3,
                            "choice": ["", "", "", ""],
                            "question_type": "TR_fill_sentence",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 15,
                            "stem": "Portraiture as an art form is more complex than is suggested by its definition.",
                            "keywords": "",
                            "paragraph": None,
                            "question_depth": 1,
                            "order": 4,
                            "choice": [
                                "The definitions of portrait art in the dictionary have regularly transformed throughout the years to reflect shifting attitudes regarding the genre.",
                                "Portraits generally mirror the conventions of the time rather than the unique qualities of the individual.",
                                "Portrait art should be considered as a distinct artistic genre due to its intense occupation with the subject and the way in which it was produced.",
                                "Throughout history, the majority of professional artists avoided portrait art since they regarded it as a mechanical art form, and not as fine art.",
                                'Beginning in the Renaissance and continuing into the start of the nineteenth century, portrait art was idealized to a greater degree than it is in today.',
                                "Portrait art was at times viewed in a negative light since it was considered as simple copying void of artistic innovation."],
                            "question_type": "TR_last_mc",
                            "choice_label": ["A", "B", "C", "D", "E", "F"],
                            "answer_weight": [1, 0, 1, 0, 1, 0],
                            "answer": [0, 0, 0, 0, 0, 0],
                            "restriction_count": 3,
                            "restriction": {
                                2: 1,
                                1: 0,
                                0: 0
                            }
                        },

                    ]
                },
            ]
        }
        return DetailResponse(data=mock, msg='获取成功')

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="get_mock/(?P<practice_id>\d+)")
    def get_mock(self, request, practice_id):
        # request send to microservices
        # input: practice
        mock = {
            'practice_id': 1,
            'is_time': True,
            'is_check_answer': False,
            'time_remain': 900,  # 秒
            'questions': [
                {
                    "question_id": 1,
                    "question_title": "Portraits as Art",
                    "questions_content": "Darwin's theory is that 'selective breeding' occurs in nature as 'natural selection' is the engine behind evolution. $$ Thus, the theory provides an excellent basis for understanding how organisms change over time. $$ Nevertheless, it is just a theory and elusively difficult to prove. One of the major holes in Darwin's theory revolves around “irreducibly complex systems.” An irreducibly complex system is known as a system where many different parts must all operate together. As a result, in the absence of one, the system as a whole collapses. Consequently, as modern technology improves, science can identify these “irreducibly complex systems” even at microscopic levels. These complex systems, if so inter-reliant, would be resistant to Darwin's supposition of how evolution occurs. As Darwin himself admitted, “To suppose that the eye with all its inimitable contrivance for adjusting the focus for different distances, for admitting different amounts of light, and for the correction of spherical and chromatic aberration, could have been formed by natural selection, seems, I free confess, absurd in the highest degree.\nIn conclusion, “On the Origin of Species” is known as one of the most consequential books ever published. Darwin's Theory of Evolution remains, to this day, a lightning rod for controversy. The theory can be observed repeatedly, but never proven, and there are a plethora of instances that cast doubt on the processes of natural selection and evolution. Darwin's conclusions were a result of keen observation and training as a naturalist. Despite the controversy that swirls around his theory, Darwin remains one of the most influential scientists and naturalists ever born due to his Theory of Evolution.",
                    "keywords": "$$",
                    "question_depth": 0,
                    "question_count": 10,
                    "children": [
                        {
                            "question_id": 2,
                            "stem": "The word “engage” in the passage is closest in meaning to",
                            "keywords": "engage",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 1,
                            "choice": ["construct", "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_sc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [1, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 3,
                            "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                            "keywords": "",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 2,
                            "choice": [
                                "Portraits representing faces are more true to life than portraits that portray a whole figure.",
                                "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_mc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 1, 0],
                            "answer": [1, 0, 0, 1],
                            "restriction_count": 2,
                            "restriction": {
                                1: 0,
                                0: 0
                            }
                        },
                        {
                            "question_id": 4,
                            "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage. \n In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "keywords": "In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 3,
                            "choice": ["", "", "", ""],
                            "question_type": "TR_fill_sentence",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [1, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 5,
                            "stem": "Portraiture as an art form is more complex than is suggested by its definition.",
                            "keywords": "",
                            "paragraph": None,
                            "question_depth": 1,
                            "order": 4,
                            "choice": [
                                "The definitions of portrait art in the dictionary have regularly transformed throughout the years to reflect shifting attitudes regarding the genre.",
                                "Portraits generally mirror the conventions of the time rather than the unique qualities of the individual.",
                                "Portrait art should be considered as a distinct artistic genre due to its intense occupation with the subject and the way in which it was produced.",
                                "Throughout history, the majority of professional artists avoided portrait art since they regarded it as a mechanical art form, and not as fine art.",
                                'Beginning in the Renaissance and continuing into the start of the nineteenth century, portrait art was idealized to a greater degree than it is in today.',
                                "Portrait art was at times viewed in a negative light since it was considered as simple copying void of artistic innovation."],
                            "question_type": "TR_last_mc",
                            "choice_label": ["A", "B", "C", "D", "E", "F"],
                            "answer_weight": [1, 0, 1, 0, 1, 0],
                            "answer": [1, 0, 0, 1, 1, 0],
                            "restriction_count": 3,
                            "restriction": {
                                2: 1,
                                1: 0,
                                0: 0
                            }
                        },

                    ]
                },
                {
                    "question_id": 6,
                    "question_title": "Portraits as Art",
                    "questions_content": "Darwin's theory is that 'selective breeding' occurs in nature as 'natural selection' is the engine behind evolution. $$ Thus, the theory provides an excellent basis for understanding how organisms change over time. $$ Nevertheless, it is just a theory and elusively difficult to prove. One of the major holes in Darwin's theory revolves around “irreducibly complex systems.” An irreducibly complex system is known as a system where many different parts must all operate together. As a result, in the absence of one, the system as a whole collapses. Consequently, as modern technology improves, science can identify these “irreducibly complex systems” even at microscopic levels. These complex systems, if so inter-reliant, would be resistant to Darwin's supposition of how evolution occurs. As Darwin himself admitted, “To suppose that the eye with all its inimitable contrivance for adjusting the focus for different distances, for admitting different amounts of light, and for the correction of spherical and chromatic aberration, could have been formed by natural selection, seems, I free confess, absurd in the highest degree.\nIn conclusion, “On the Origin of Species” is known as one of the most consequential books ever published. Darwin's Theory of Evolution remains, to this day, a lightning rod for controversy. The theory can be observed repeatedly, but never proven, and there are a plethora of instances that cast doubt on the processes of natural selection and evolution. Darwin's conclusions were a result of keen observation and training as a naturalist. Despite the controversy that swirls around his theory, Darwin remains one of the most influential scientists and naturalists ever born due to his Theory of Evolution.",
                    "keywords": "$$",
                    "question_depth": 0,
                    "question_count": 10,
                    "children": [
                        {
                            "question_id": 7,
                            "stem": "The word “engage” in the passage is closest in meaning to",
                            "keywords": "engage",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 1,
                            "choice": ["construct", "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_sc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 1, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 8,
                            "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                            "keywords": "",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 2,
                            "choice": [
                                "Portraits representing faces are more true to life than portraits that portray a whole figure.",
                                "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_mc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 1, 0],
                            "answer": [1, 0, 0, 0],
                            "restriction_count": 2,
                            "restriction": {
                                1: 0,
                                0: 0
                            }
                        },
                        {
                            "question_id": 9,
                            "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage. \n In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "keywords": "In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 3,
                            "choice": ["", "", "", ""],
                            "question_type": "TR_fill_sentence",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 10,
                            "stem": "Portraiture as an art form is more complex than is suggested by its definition.",
                            "keywords": "",
                            "paragraph": None,
                            "question_depth": 1,
                            "order": 4,
                            "choice": [
                                "The definitions of portrait art in the dictionary have regularly transformed throughout the years to reflect shifting attitudes regarding the genre.",
                                "Portraits generally mirror the conventions of the time rather than the unique qualities of the individual.",
                                "Portrait art should be considered as a distinct artistic genre due to its intense occupation with the subject and the way in which it was produced.",
                                "Throughout history, the majority of professional artists avoided portrait art since they regarded it as a mechanical art form, and not as fine art.",
                                'Beginning in the Renaissance and continuing into the start of the nineteenth century, portrait art was idealized to a greater degree than it is in today.',
                                "Portrait art was at times viewed in a negative light since it was considered as simple copying void of artistic innovation."],
                            "question_type": "TR_last_mc",
                            "choice_label": ["A", "B", "C", "D", "E", "F"],
                            "answer_weight": [1, 0, 1, 0, 1, 0],
                            "answer": [1, 0, 1, 0, 1, 0],
                            "restriction_count": 3,
                            "restriction": {
                                2: 1,
                                1: 0,
                                0: 0
                            }
                        },

                    ]
                },
                {
                    "question_id": 11,
                    "question_title": "Portraits as Art",
                    "questions_content": "Darwin's theory is that 'selective breeding' occurs in nature as 'natural selection' is the engine behind evolution. $$ Thus, the theory provides an excellent basis for understanding how organisms change over time. $$ Nevertheless, it is just a theory and elusively difficult to prove. One of the major holes in Darwin's theory revolves around “irreducibly complex systems.” An irreducibly complex system is known as a system where many different parts must all operate together. As a result, in the absence of one, the system as a whole collapses. Consequently, as modern technology improves, science can identify these “irreducibly complex systems” even at microscopic levels. These complex systems, if so inter-reliant, would be resistant to Darwin's supposition of how evolution occurs. As Darwin himself admitted, “To suppose that the eye with all its inimitable contrivance for adjusting the focus for different distances, for admitting different amounts of light, and for the correction of spherical and chromatic aberration, could have been formed by natural selection, seems, I free confess, absurd in the highest degree.\nIn conclusion, “On the Origin of Species” is known as one of the most consequential books ever published. Darwin's Theory of Evolution remains, to this day, a lightning rod for controversy. The theory can be observed repeatedly, but never proven, and there are a plethora of instances that cast doubt on the processes of natural selection and evolution. Darwin's conclusions were a result of keen observation and training as a naturalist. Despite the controversy that swirls around his theory, Darwin remains one of the most influential scientists and naturalists ever born due to his Theory of Evolution.",
                    "keywords": "$$",
                    "question_depth": 0,
                    "question_count": 10,
                    "children": [
                        {
                            "question_id": 12,
                            "stem": "The word “engage” in the passage is closest in meaning to",
                            "keywords": "engage",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 1,
                            "choice": ["construct", "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_sc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 13,
                            "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                            "keywords": "",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 2,
                            "choice": [
                                "Portraits representing faces are more true to life than portraits that portray a whole figure.",
                                "are pleased", "are altered", "are involved in"],
                            "question_type": "TR_mc",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 1, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 2,
                            "restriction": {
                                1: 0,
                                0: 0
                            }
                        },
                        {
                            "question_id": 14,
                            "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage. \n In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "keywords": "In certain instances, portrait artists depended on a combination of direct and indirect involvement with their subjects",
                            "paragraph": 1,
                            "question_depth": 1,
                            "order": 3,
                            "choice": ["", "", "", ""],
                            "question_type": "TR_fill_sentence",
                            "choice_label": ["A", "B", "C", "D"],
                            "answer_weight": [1, 0, 0, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 1,
                        },
                        {
                            "question_id": 15,
                            "stem": "Portraiture as an art form is more complex than is suggested by its definition.",
                            "keywords": "",
                            "paragraph": None,
                            "question_depth": 1,
                            "order": 4,
                            "choice": [
                                "The definitions of portrait art in the dictionary have regularly transformed throughout the years to reflect shifting attitudes regarding the genre.",
                                "Portraits generally mirror the conventions of the time rather than the unique qualities of the individual.",
                                "Portrait art should be considered as a distinct artistic genre due to its intense occupation with the subject and the way in which it was produced.",
                                "Throughout history, the majority of professional artists avoided portrait art since they regarded it as a mechanical art form, and not as fine art.",
                                'Beginning in the Renaissance and continuing into the start of the nineteenth century, portrait art was idealized to a greater degree than it is in today.',
                                "Portrait art was at times viewed in a negative light since it was considered as simple copying void of artistic innovation."],
                            "question_type": "TR_last_mc",
                            "choice_label": ["A", "B", "C", "D", "E", "F"],
                            "answer_weight": [1, 0, 1, 0, 1, 0],
                            "answer": [0, 0, 0, 0],
                            "restriction_count": 3,
                            "restriction": {
                                2: 1,
                                1: 0,
                                0: 0
                            }
                        },
                    ]
                },
            ]
        }
        return DetailResponse(data=mock, msg='获取成功')

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="answer_status/(?P<practice_id>\d+)")
    def get_answer_status(self, request, practice_id):
        response = [
            {
                "order": 1,
                "stem": "The word “engage” in the passage is closest in meaning to",
                "is_answer": True,
            },
            {
                "order": 2,
                "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                "is_answer": True,
            },
            {
                "order": 3,
                "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                "is_answer": True,
            },
            {
                "order": 4,
                "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                "is_answer": True,
            },
            {
                "order": 5,
                "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                "is_answer": True,
            },
            {
                "order": 6,
                "stem": "Look at the four squares 【   】 that indicate where the following sentence could be added to the passage. Where would the sentence best fit? Click on a square 【   】to add the sentence to the passage.",
                "is_answer": False,
            },
            {
                "order": 1,
                "stem": "According to paragraph 1，which of the following gives support of portrait painting's complexity?",
                "is_answer": False,
            }
        ]
        return DetailResponse(data=response, msg='获取成功')

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def answer_panel(self, request):
        question_id = request.data.get('question_id')
        answer = request.data.get('answer')
        try:
            answer = list(answer)
            return DetailResponse(data=[], msg='OK.')
        except:
            return ErrorResponse(msg='参数格式错误')

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def submit_answers(self, request):
        question_id = request.data.get('practice_id')
        try:
            return DetailResponse(data=[], msg='提交成功.')
        except:
            return ErrorResponse(msg='参数格式错误')


