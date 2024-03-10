from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from blueprints.learning.controllers import VocabLearningController, TaskController
import json
from utils.redis_tools import RedisWrapper
import uuid as u
from datetime import datetime, timezone, timedelta, date

bp = Blueprint('learning_api', __name__, url_prefix='/v1/api/learning/')


# ----------------------------------------   单词任务  ---------------------------------------- #
@bp.route('get_vocabs_statics/<account_id>/', methods=['GET'])
def get_vocabs_statics(account_id):
    try:
        res, data = VocabLearningController().fetch_account_vocab(
            account_id=account_id
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_today_vocab_task/<account_id>/', methods=['GET'])
def get_today_vocab_task(account_id):
    try:
        today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        time = datetime(today.year, today.month, today.day, 0, 0)
        res, data = TaskController().fetch_account_tasks(
            account_id=account_id,
            after_time=time,
            type=1,
            is_complete=0,
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')

@bp.route('create_new_vocab_tasks/<account_id>/', methods=['GET'])
def create_new_vocab_tasks(account_id):
    try:
        res, data = VocabLearningController().create_new_vocab_tasks(
            account_id=account_id,
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')

@bp.route('start_task/', methods=['POST'])
def start_task():
    try:
        args = request.json
        task_account_id = args.get('task_account_id')
        res, data = TaskController().start_task(
            task_account_id=task_account_id,
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')

@bp.route('learning_task/', methods=['POST'])
def learning_task():
    try:
        args = request.json
        task_account_id = args.get('task_account_id')
        payload = args.get('payload')
        res, data = TaskController().rec_module_outcome(
            task_account_id=task_account_id,
            payload=payload
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


