from application import settings

# ================================================= #
# ***************** 插件配置区开始 *******************
# ================================================= #
# 路由配置
plugins_url_patterns = [
    {"re_path": r'api/sms/', "include": "dvadmin_sms.urls"},
]
# app 配置
apps = ['dvadmin_sms']

# ================================================= #
# ******************* 插件配置区结束 *****************
# ================================================= #

# ********** 赋值到 settings 中 **********
settings.INSTALLED_APPS += [app for app in apps if app not in settings.INSTALLED_APPS]

# ********** 注册路由 **********
settings.PLUGINS_URL_PATTERNS += plugins_url_patterns
