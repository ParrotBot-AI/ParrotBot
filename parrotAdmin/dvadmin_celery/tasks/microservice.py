# ======== 用于微服务的任务 ========#

from application.celery import app
from dvadmin.system.model import MicroServiceRegister
from dvadmin.system.views.microservice import MicroServiceCreateUpdateSerializer
import requests
import time

@app.task
def check_heart_beat(name):
    service = MicroServiceRegister.objects.filter(name=name)
    if service.status == 1:
        url = f"{service.host}/{service.port}/{service.heartBeatApi}"
        method = service.method
        if method == "GET":
            response = requests.get(url)
            if response.status_code != 200:
                # 3 秒后再次请求
                time.sleep(3)
                response = requests.get(url)
                if response.status_code != 200:
                    ##########################
                    # to do, 发送email至管理员 #
                    ##########################

                    # 更新该应用状态
                    updated = {
                        "status": 0,
                    }
                    serializer = MicroServiceCreateUpdateSerializer(service, data=updated)
                    if serializer.is_valid():
                        serializer.save()
                        print(f"检测应用{service.name}心跳失败.")