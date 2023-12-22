from django.contrib import admin
# from models import (
#     Users,
#     Dept,
#     Dictionary,
#     Role,
#     Menu,
#     MenuButton,
#     OperationLog,
#     FileList,
#     Area,
#     ApiWhiteList,
#     SystemConfig,
#     LoginLog,
#     MessageCenter,
#     MessageCenterTargetUser,
# )
from django.apps import apps
from .models import *
from django.contrib import admin

app = apps.get_app_config('system')

# Register your models here.
for model_name, model in app.models.items():
    print(model_name)
    admin.site.register(model)


