from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from blueprints.account.controllers import AccountController
import json
from utils.redis_tools import RedisWrapper
import uuid as u

bp = Blueprint('account_api', __name__, url_prefix='/v1/api/account/')


@bp.route('get_menu_exam', methods=['POST'])
def get_menu_exam():
    try:
        args = request.json
        menu_ids = args.get('menu_id')  # list
        print(menu_ids, 16)
        res = AccountController().get_menu_exams(
            menu_ids=menu_ids
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')
