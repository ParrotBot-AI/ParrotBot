from dvadmin.utils.client_info import get_client_ip, get_host
from dvadmin.utils.json_response import ErrorResponse, DetailResponse
from rest_framework.decorators import action
from django.core.cache import cache
from dvadmin.utils.stream_controllers import AdminStream
import random

class Streaming:
    @action(methods=["GET"], detail=False, permission_classes=[])
    def test_streaming(self, request):
        """
        测试streaming
        """
        AdminStream.admin_action("account_register", test={"core": str(True), "test": str(True)})
        return DetailResponse(msg='OK', data={})