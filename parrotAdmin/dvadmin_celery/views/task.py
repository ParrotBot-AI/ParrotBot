# -*- coding: utf-8 -*-

"""
@author: 阿辉
@contact: QQ:2655399832
@Created on: 2022/9/21 16:30
@Remark:
"""
import uuid

from django_celery_beat.models import PeriodicTask, CrontabSchedule, cronexp
from rest_framework.exceptions import APIException
from rest_framework import serializers

from dvadmin.utils.serializers import CustomModelSerializer
from dvadmin.utils.viewset import CustomModelViewSet
from dvadmin.utils.json_response import SuccessResponse, ErrorResponse

CrontabSchedule.__str__ = lambda self: '{0} {1} {2} {3} {4} {5}'.format(
    cronexp(self.minute), cronexp(self.hour),
    cronexp(self.day_of_month), cronexp(self.month_of_year),
    cronexp(self.day_of_week), str(self.timezone)
)


def get_job_list():
    from application import settings
    task_list = []
    task_dict_list = []
    for app in settings.INSTALLED_APPS:
        try:
            exec(f"""
from {app} import tasks
for ele in [i for i in dir(tasks) if i.startswith('task__')]:
    task_dict = dict()
    task_dict['label'] = '{app}.tasks.' + ele
    task_dict['value'] = '{app}.tasks.' + ele
    task_list.append('{app}.tasks.' + ele)
    task_dict_list.append(task_dict)
                """)
        except ImportError:
            pass
    return {'task_list': task_list, 'task_dict_list': task_dict_list}


# 将cron表达式进行解析
def CronSlpit(cron):
    cron = cron.split(" ")
    result = {
        # "second":cron[0],
        "minute": cron[0],
        "hour": cron[1],
        "day": cron[2],
        "month": cron[3],
        "week": cron[4]
    }
    return result


class CeleryCrontabScheduleSerializer(CustomModelSerializer):
    class Meta:
        model = CrontabSchedule
        exclude = ('timezone',)


class PeriodicTasksSerializer(CustomModelSerializer):
    crontab = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PeriodicTask
        fields = '__all__'


class CeleryTaskModelViewSet(CustomModelViewSet):
    """
    CeleryTask 添加任务调度
    """

    queryset = PeriodicTask.objects.exclude(name="celery.backend_cleanup")
    serializer_class = PeriodicTasksSerializer
    filter_fields = ['name', 'task', 'enabled']

    # permission_classes = []
    # authentication_classes = []

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, request=request)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True, request=request)
        return SuccessResponse(data=serializer.data, msg="获取成功")

    def job_list(self, request, *args, **kwargs):
        """获取所有任务"""
        result = get_job_list()
        task_list = result.get('task_dict_list')
        return SuccessResponse(msg='获取成功', data=task_list, total=len(task_list))

    def create(self, request, *args, **kwargs):
        body_data = request.data.copy()
        cron = body_data.get('crontab')
        cron_lisr = CronSlpit(cron)
        minute = cron_lisr["minute"]
        hour = cron_lisr["hour"]
        day = cron_lisr["day"]
        month = cron_lisr["month"]
        week = cron_lisr["week"]
        cron_data = {
            'minute': minute,
            'hour': hour,
            'day_of_week': week,
            'day_of_month': day,
            'month_of_year': month
        }
        task = body_data.get('task')
        result = None
        task_list = get_job_list()
        task_list = task_list.get('task_list')
        if task in task_list:
            # job_name = task.split('.')[-1]
            # path_name = '.'.join(task.split('.')[:-1])

            # 添加crontab
            serializer = CeleryCrontabScheduleSerializer(data=cron_data, request=request)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

            # 添加任务
            body_data['crontab'] = serializer.data.get('id')
            body_data['enabled'] = False
            serializer = self.get_serializer(data=body_data, request=request)
            res = serializer.is_valid()
            if not res:
                raise APIException({"msg": f"添加失败，已经有一个名为 {body_data['name']} 的任务了"}, code=4000)
            self.perform_create(serializer)
            result = serializer.data
            return SuccessResponse(msg="添加成功", data=result)
        else:
            return ErrorResponse(msg="添加失败,没有该任务", data=None)

    def destroy(self, request, *args, **kwargs):
        """删除定时任务"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return SuccessResponse(data=[], msg="删除成功")

    def update_status(self, request, *args, **kwargs):
        """开始/暂停任务"""
        instance = self.get_object()
        body_data = request.data
        instance.enabled = body_data.get('enabled')
        instance.save()
        return SuccessResponse(msg="修改成功", data=None)
