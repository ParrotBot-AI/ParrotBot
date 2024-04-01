from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from blueprints.learning.controllers import VocabLearningController, TaskController, StudyPulseController
from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session
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


@bp.route('jump_vocabs/', methods=['POST'])
def jump_vocabs():
    try:
        args = request.json
        account_id = args.get('account_id')
        category = args.get('category_id')
        exam = args.get('exam_id')
        if not exam:
            res, data = VocabLearningController().jump_to_vocabs(
                account_id=account_id,
                category_id=category,
            )
        else:
            res, data = VocabLearningController().jump_to_vocabs(
                account_id=account_id,
                category_id=category,
                exam_id=exam
            )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('reset_vocabs/<account_id>/', methods=['POST'])
def reset_vocabs(account_id):
    try:
        res, data = VocabLearningController().reset_vocabs(
            account_id=account_id,
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('refuse_jump/<account_id>/', methods=['POST'])
def refuse_jump(account_id):
    try:
        res, data = VocabLearningController().refuse_jump(
            account_id=account_id,
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


# ----------------------------------------   任务总览  ---------------------------------------- #

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


@bp.route('get_today_tasks/<user_id>/', methods=['GET'])
def get_today_task(user_id):
    from blueprints.account.models import Users, Accounts
    with db_session('core') as session:
        user_record = (
            session.query(Users)
            .filter(Users.user_id == user_id)
            .one_or_none()
        )
        if not user_record:
            return ArgumentExceptionResponse(msg=f'user未找到')
        user_inx = user_record.id
        accounts = (
            session.query(Accounts)
            .filter(Accounts.user_id == user_inx)
            .all()
        )
        try:
            today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            time = datetime(today.year, today.month, today.day, 0, 0)
            _res = []
            for account in accounts:
                res, data = TaskController().fetch_account_tasks(
                    account_id=account.id,
                    after_time=time,
                )
                if res:
                    for each in data:
                        each['exam_id'] = account.exam_id

                    _res = _res + data
                else:
                    return ArgumentExceptionResponse(msg=f'{data}')

            return SuccessDataResponse(_res)
        except Exception as e:
            return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('add_pulse_time/<account_id>/', methods=['POST'])
def add_pulse_time(account_id):
    try:
        args = request.json
        time_length = args.get('time_length')
        res, data = StudyPulseController().add_pulse_time(
            account_id=account_id,
            time_length=time_length if time_length is not None else None,
        )
        if res:
            return SuccessDataResponse(data)
        else:
            return ArgumentExceptionResponse(msg=f'{data}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_checkin_info/<account_id>/', methods=['GET'])
def get_checkin_info(account_id):
    from blueprints.account import AccountController
    try:
        res, data = StudyPulseController().get_pulse_check_information(
            account_id=account_id,
        )
        if not res:
            return ArgumentExceptionResponse(msg=f'{data}')

        res_, data_ = AccountController().account_additional_info(
            account_id=account_id,
        )
        if not res_:
            return ArgumentExceptionResponse(msg=f'{data}')

        data['info'] = data_
        return SuccessDataResponse(data)

    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')
