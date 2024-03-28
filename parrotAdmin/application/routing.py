# -*- coding: utf-8 -*-
from django.urls import path
from application.websocketConfig import MegCenter, QuestionWebSocket, StudyGeneralWebSocket

websocket_urlpatterns = [
    path('ws/<str:service_uid>/', MegCenter.as_asgi()),  # consumers.DvadminWebSocket 是该路由的消费者
    path('ws/question/<str:service_uid>/<str:account_id>/<str:sheet_id>', QuestionWebSocket.as_asgi()),  # consumers.QuestionWebSocket 是该路由的消费者
    path('ws/study/<str:service_uid>/<str:account_id>/', StudyGeneralWebSocket.as_asgi()),  # consumers.QuestionWebSocket 是该路由的消费者
]
