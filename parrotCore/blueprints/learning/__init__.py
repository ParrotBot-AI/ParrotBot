from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from blueprints.learning.controllers import VocabLearningController
import json
from utils.redis_tools import RedisWrapper
import uuid as u

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