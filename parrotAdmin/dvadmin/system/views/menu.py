# -*- coding: utf-8 -*-

"""
@author: 猿小天
@contact: QQ:1638245306
@Created on: 2021/6/1 001 22:38
@Remark: 菜单模块
"""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from dvadmin.system.models import Menu, MenuButton, MicroServiceRegister
from dvadmin.system.views.menu_button import MenuButtonInitSerializer
# from dvadmin.system.views.microservice import MicroServiceRegisterSerializer
from dvadmin.utils.json_response import SuccessResponse, ErrorResponse, DetailResponse
from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.viewset import CustomModelViewSet
import requests


class UserMenuSerializer(CustomModelSerializer):
    """
    菜单表的简单序列化器
    """
    menuPermission = serializers.SerializerMethodField(read_only=True)
    hasChild = serializers.SerializerMethodField()

    def get_hasChild(self, instance):
        hasChild = Menu.objects.filter(parent=instance.id)
        if hasChild:
            return True
        return False

    def get_menuPermission(self, instance):
        queryset = instance.menuPermission.order_by('-name').values_list('name', flat=True)
        if queryset:
            return queryset
        else:
            return None

    class Meta:
        model = Menu
        fields = ['id', 'name', 'icon', 'is_catalog', 'web_path', 'parent', 'hasChild', 'menuPermission']
        read_only_fields = ["id"]


class MenuSerializer(CustomModelSerializer):
    """
    菜单表的简单序列化器
    """
    menuPermission = serializers.SerializerMethodField(read_only=True)
    hasChild = serializers.SerializerMethodField()

    def get_menuPermission(self, instance):
        queryset = instance.menuPermission.order_by('-name').values_list('name', flat=True)
        if queryset:
            return queryset
        else:
            return None

    def get_hasChild(self, instance):
        hasChild = Menu.objects.filter(parent=instance.id)
        if hasChild:
            return True
        return False

    class Meta:
        model = Menu
        fields = "__all__"
        read_only_fields = ["id"]


class MenuCreateSerializer(CustomModelSerializer):
    """
    菜单表的创建序列化器
    """
    name = serializers.CharField(required=False)

    class Meta:
        model = Menu
        fields = "__all__"
        read_only_fields = ["id"]


class MenuInitSerializer(CustomModelSerializer):
    """
    递归深度获取数信息(用于生成初始化json文件)
    """
    name = serializers.CharField(required=False)
    children = serializers.SerializerMethodField()
    menu_button = serializers.SerializerMethodField()

    def get_children(self, obj: Menu):
        data = []
        instance = Menu.objects.filter(parent_id=obj.id)
        if instance:
            serializer = MenuInitSerializer(instance=instance, many=True)
            data = serializer.data
        return data

    def get_menu_button(self, obj: Menu):
        data = []
        instance = obj.menuPermission.order_by('method')
        if instance:
            data = list(instance.values('name', 'value', 'api', 'method'))
        return data

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        children = self.initial_data.get('children')
        menu_button = self.initial_data.get('menu_button')
        # 菜单表
        if children:
            for menu_data in children:
                menu_data['parent'] = instance.id
                filter_data = {
                    "name": menu_data['name'],
                    "web_path": menu_data['web_path'],
                    "component": menu_data['component'],
                    "component_name": menu_data['component_name'],
                }
                instance_obj = Menu.objects.filter(**filter_data).first()
                if instance_obj and not self.initial_data.get('reset'):
                    continue
                serializer = MenuInitSerializer(instance_obj, data=menu_data, request=self.request)
                serializer.is_valid(raise_exception=True)
                serializer.save()
        # 菜单按钮
        if menu_button:
            for menu_button_data in menu_button:
                menu_button_data['menu'] = instance.id
                filter_data = {
                    "menu": menu_button_data['menu'],
                    "value": menu_button_data['value']
                }
                instance_obj = MenuButton.objects.filter(**filter_data).first()
                serializer = MenuButtonInitSerializer(instance_obj, data=menu_button_data, request=self.request)
                serializer.is_valid(raise_exception=True)
                serializer.save()
        return instance

    class Meta:
        model = Menu
        fields = ['name', 'icon', 'sort', 'is_link', 'is_catalog', 'web_path', 'component', 'component_name', 'status',
                  'cache', 'visible', 'parent', 'children', 'menu_button', 'frame_out', 'creator', 'dept_belong_id']
        extra_kwargs = {
            'creator': {'write_only': True},
            'dept_belong_id': {'write_only': True}
        }
        read_only_fields = ['id', 'children']


class WebRouterSerializer(CustomModelSerializer):
    """
    前端菜单路由的简单序列化器
    """
    path = serializers.CharField(source="web_path")
    title = serializers.CharField(source="name")
    menuPermission = serializers.SerializerMethodField(read_only=True)

    def get_menuPermission(self, instance):
        # 判断是否是超级管理员
        if self.request.user.is_superuser:
            return instance.menuPermission.values_list('value', flat=True)
        else:
            # 根据当前角色获取权限按钮id集合
            permissionIds = self.request.user.role.values_list('permission', flat=True)
            queryset = instance.menuPermission.filter(id__in=permissionIds, menu=instance.id).values_list('value',
                                                                                                          flat=True)
            if queryset:
                return queryset
            else:
                return None

    class Meta:
        model = Menu
        fields = (
            'id', 'parent', 'icon', 'sort', 'path', 'name', 'title', 'is_link', 'is_catalog', 'web_path', 'component',
            'component_name', 'cache', 'visible', 'menuPermission', 'frame_out')
        read_only_fields = ["id"]


class MenuViewSet(CustomModelViewSet):
    """
    菜单管理接口
    list:查询
    create:新增
    update:修改
    retrieve:单例
    destroy:删除
    """
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    create_serializer_class = MenuCreateSerializer
    update_serializer_class = MenuCreateSerializer
    search_fields = ['name', 'status']
    filter_fields = ['parent', 'name', 'status', 'is_link', 'visible', 'cache', 'is_catalog']

    # extra_filter_backends = []
    @action(methods=['GET'], detail=False, permission_classes=[IsAuthenticated],
            url_path="user_menu/(?P<menu_id>\d+)"
            )
    def get_user_menu(self, request, menu_id):
        """用于前端获取当前角色的路由(用户端)"""
        print(menu_id)
        if menu_id:
            queryset = self.queryset.filter(status=1, user_use=1, visible=1, parent_id=menu_id).all()
            serializer = UserMenuSerializer(queryset, many=True, request=request)
            data = serializer.data
            return SuccessResponse(data=data, total=len(data), msg="获取成功")
        else:
            return SuccessResponse(data=[], total=0, msg="获取成功")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated],
            url_path="user_menu(?:/(?P<menu_id>\d+))?")
    # @action(methods=['GET'], detail=False, permission_classes=[IsAuthenticated],)
    def user_menu(self, request, menu_id=None):
        """用于前端获取当前角色的路由(用户端)"""
        # menu_id = request.data.get("menu_id")
        if menu_id:
            queryset = self.queryset.filter(status=1, user_use=1, visible=1, parent_id=menu_id).all()
            serializer = UserMenuSerializer(queryset, many=True, request=request)
            data = serializer.data
            return SuccessResponse(data=data, total=len(data), msg="获取成功")
        else:
            # 直接跳过考试层
            # request for toefl exam id
            # to do
            exam_id = 1
            queryset = self.queryset.filter(status=1, user_use=1, visible=1, name='托福').first()
            tuofu_id = queryset.id
            queryset = self.queryset.filter(status=1, user_use=1, visible=1, parent_id=tuofu_id).all()
            # queryset = self.queryset.filter(status=1, user_use=1, visible=1, parent__isnull=True).all()
            serializer = UserMenuSerializer(queryset, many=True, request=request)

            menu_ids = [each['id'] for each in serializer.data]
            # micro_q = MicroServiceRegister.objects.filter(name='ParrotCore', status=1)
            # micro = MicroServiceRegisterSerializer(micro_q, many=False, request=request)
            if True:
                # data = dict(micro.data)
                url = f"http://{'127.0.0.1'}:{10981}/v1/api/account/get_menu_exam/"
                r = requests.post(url, json={
                    'menu_id': menu_ids,
                })

                if r.json()['code'] == 10000:
                    res_data = r.json()['data']
                else:
                    return ErrorResponse(msg="微服务故障")

            response = [dict(item) for item in serializer.data]
            menu_id_to_pattern_id = {item['menu_id']: item['pattern_id'] for item in res_data}
            for item in response:
                item['pattern_id'] = menu_id_to_pattern_id.get(item['id'], None)

            return SuccessResponse(data=response, total=len(response), msg="获取成功")

    @action(methods=['GET'], detail=False, permission_classes=[])
    def web_router(self, request):
        """用于前端获取当前角色的路由"""
        user = request.user
        queryset = self.queryset.filter(status=1)
        if not user.is_superuser:
            menuIds = user.role.values_list('menu__id', flat=True)
            queryset = Menu.objects.filter(id__in=menuIds, status=1)
        serializer = WebRouterSerializer(queryset, many=True, request=request)
        data = serializer.data
        return SuccessResponse(data=data, total=len(data), msg="获取成功")

    @action(methods=['GET'], detail=False, permission_classes=[IsAuthenticated])
    def menu_ad(self, request):
        data = {
            "url": "https://obs-parrotcore.obs.cn-east-3.myhuaweicloud.com/9.9%E5%85%83%E4%BC%9A%E5%91%98%E7%A4%BC%E5%8C%85.png"
        }
        return DetailResponse(data=data, msg="获取成功")


    def list(self, request):
        """懒加载"""
        params = request.query_params
        parent = params.get('parent', None)
        if params:
            if parent:
                queryset = self.queryset.filter(parent=parent)
            else:
                queryset = self.queryset
        else:
            queryset = self.queryset.filter(parent__isnull=True)
        queryset = self.filter_queryset(queryset)
        serializer = MenuSerializer(queryset, many=True, request=request)
        data = serializer.data
        return SuccessResponse(data=data)
