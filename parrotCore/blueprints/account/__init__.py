from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from blueprints.account.controllers import AccountController
from datetime import datetime
bp = Blueprint('account_api', __name__, url_prefix='/v1/api/account/')


@bp.route('get_menu_exam/', methods=['POST'])
def get_menu_exam():
    try:
        args = request.json
        menu_ids = args.get('menu_id')  # list
        res = AccountController().get_menu_exams(
            menu_ids=menu_ids
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('register_user/', methods=['POST'])
def register_user():
    try:
        args = request.json
        exam_ids = args.get('exam_ids', [1])  # list
        user_id = args.get('user_id')
        res = AccountController().register_user(
            user_id=user_id,
            exam_ids=exam_ids
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('questionnaire/', methods=['POST'])
def questionnaire():
    try:
        args = request.json
        account_id = args.get('account_id')
        purpose = args.get('purpose')  # list
        status = args.get('status')
        study_type = args.get('study_type')
        next_exam_date = args.get('next_exam_date')

        param = dict(
            current_status=status,
            purpose=purpose,
            study_type=study_type,
            next_test_time=datetime.strptime(next_exam_date, '%Y-%m-%d').date() if next_exam_date else None
        )

        res = AccountController().update_questionary(
            account_id=account_id,
            param=param
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_user_accounts/<user_id>/', methods=['POST'])
def get_user_accounts(user_id):
    try:
        args = request.json
        exam_id = args.get('exam_id')  # list
        res = AccountController().get_user_accounts(
            user_id=user_id,
            exam_id=exam_id
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_user_info/<user_id>/', methods=['GET'])
def get_user_info(user_id):
    try:
        res = AccountController().get_user_info(
            user_id=user_id
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')
