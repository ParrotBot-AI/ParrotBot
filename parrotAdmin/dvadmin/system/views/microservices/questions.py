# -*- coding: utf-8 -*-

"""
@author: hhhhzl
@Created on: 2024/1/24 001 22:38
@Remark 微服务问题模块
"""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from dvadmin.system.views.menu_button import MenuButtonInitSerializer
from dvadmin.utils.json_response import SuccessResponse
from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.viewset import CustomModelViewSet


@action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
def resource(self, request):
    exam_id = request.data.get("exam_id")
    pattern_id = request.data.get("pattern_id")
    # whether_zt = request.data.get("is_real_problem") # 目前默认false
    whether_zt = False

    # request send to microservices
    # input: exam_id, pattern_id, whether_zt
    # output: resource list with sub question

    resource = [
        {
            "resource_id":1,
            "resource_parent_name":"TPO 1",
            "resource_name": "TPO 1-阅读",
            "sections":
                [
                    {
                    "section_id":1,
                    "section_name":"第一篇阅读",
                    "questions":[
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
    return SuccessResponse(data=resource, msg='获取成功')
