# 初始化
import os

import django

from dvadmin.system.views.system_config import SystemConfigInitSerializer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "application.settings")
django.setup()

from dvadmin.system.views.menu import MenuInitSerializer
from dvadmin.utils.core_initialize import CoreInitialize
from dvadmin.system.views.dictionary import DictionaryInitSerializer


class Initialize(CoreInitialize):

    def init_menu(self):
        """
        初始化菜单信息
        """
        self.init_base(MenuInitSerializer, unique_fields=['name', 'web_path', 'component', 'component_name'])

    def init_dictionary(self):
        """
        初始化字典表
        """
        self.init_base(DictionaryInitSerializer, unique_fields=['value', 'parent', ])

    def init_system_config(self):
        """
        初始化系统配置表
        """
        self.init_base(SystemConfigInitSerializer, unique_fields=['key', 'parent', ])

    def run(self):
        self.init_menu()
        self.init_dictionary()
        self.init_system_config()


if __name__ == "__main__":
    Initialize(app='dvadmin.system').run()
