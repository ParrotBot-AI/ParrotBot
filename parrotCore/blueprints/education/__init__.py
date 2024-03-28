from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from blueprints.education.controllers import QuestionController, AnsweringScoringController, TransactionsController
import json
from utils.redis_tools import RedisWrapper
import uuid as u

bp = Blueprint('education_api', __name__, url_prefix='/v1/api/education/')


# ----------------------------------------   题库资源  ---------------------------------------- #
@bp.route('fetch_resource/<account_id>/', methods=['GET'])
def fetch_resource(account_id):
    try:
        # res = TransactionsController()._get_all_resources_under_patterns(
        #     pattern_id=pattern_id,
        #     account_id=account_id
        # )
        res = True, []
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('fetch_resource_p/<account_id>/<pattern_id>/', methods=['POST'])
def fetch_resource_p(account_id, pattern_id):
    args = request.json
    page = args.get('page')
    limit = args.get('limit')
    try:
        res = TransactionsController()._get_all_resources_under_patterns(
            pattern_id=pattern_id,
            account_id=account_id,
            page=page,
            limit=limit,
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('fetch_resource_e/<account_id>/<exam_id>/', methods=['POST'])
def fetch_resource_e(account_id, exam_id):
    args = request.json
    page = args.get('page')
    limit = args.get('limit')
    try:
        res = TransactionsController()._get_all_resources_under_exams(
            exam_id=exam_id,
            account_id=account_id,
            page=page,
            limit=limit,
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('fetch_past_scores/<account_id>/', methods=['GET'])
def fetch_past_scores(account_id):
    try:
        res = TransactionsController().get_recent_pattern_scores(
            account_id=account_id,
            offset=14
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


# ----------------------------------------   做题   ---------------------------------------- #
@bp.route('create_mock_sheet', methods=['POST'])
def create_mock_sheet():
    try:
        args = request.json
        account_id = args.get('account_id')
        res = AnsweringScoringController().create_mock_answer_sheet(
            account_id=account_id,
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('pause_sheet/<sheet_id>/', methods=['POST'])
def pause_sheet(sheet_id):
    try:
        res = AnsweringScoringController().pause_sheet(
            sheet_id=sheet_id,
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('create_sheet', methods=['POST'])
def create_sheet():
    try:
        args = request.json
        account_id = args.get('account_id')
        q_type = args.get('q_type')
        question_ids = args.get('question_ids')
        father_sheet = args.get('father_sheet')
        res = AnsweringScoringController().create_answer_sheet(
            account_id=account_id,
            type=q_type,
            question_ids=question_ids,
            father_sheet=father_sheet
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_mock_sheet/<sheet_id>/', methods=['GET'])
def get_mock_sheet(sheet_id):
    try:
        args = request.json
        con = args.get('continue')
        res = AnsweringScoringController().get_mock_answer_sheet(
            sheet_id=sheet_id,
            contin=True if con == True else False
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_sheet/<sheet_id>/', methods=['GET'])
def get_sheet(sheet_id):
    try:
        args = request.json
        con = args.get('continue')
        res = AnsweringScoringController().get_test_answers(
            sheet_id=sheet_id,
            contin=True if con == True else False
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_sheet_status/<sheet_id>/', methods=['GET'])
def get_sheet_status(sheet_id):
    try:
        res = AnsweringScoringController().get_sheet_status(
            sheet_id=sheet_id
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('update_ans', methods=['POST'])
def update_ans():
    try:
        args = request.json
        sheet_id = args.get('sheet_id')
        duration = args.get('duration')
        answer = args.get('answer')
        question_id = args.get('question_id')
        answer_voice_link = args.get('answer_voice_link')
        answer_video_link = args.get('answer_video_link')
        upload_file = args.get('upload_file')

        res = AnsweringScoringController().update_question_answer(
            sheet_id=sheet_id,
            question_id=question_id,
            answer=answer,
            answer_voice_link=answer_voice_link,
            answer_video_link=answer_video_link,
            upload_file_link=upload_file,
            duration=duration
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('save_answer/<sheet_id>/', methods=['POST'])
def save_answer(sheet_id):
    try:
        res = AnsweringScoringController().save_answer(
            sheet_id=sheet_id
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('scoring/<sheet_id>/', methods=['POST'])
def scoring(sheet_id):
    args = request.json
    redo = args.get('redo')
    try:
        res = AnsweringScoringController().scoring(
            sheet_id=sheet_id,
            re_score=redo
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_score/<sheet_id>/', methods=['GET'])
def get_score(sheet_id):
    try:
        res = AnsweringScoringController().get_score(
            answer_sheet_id=sheet_id,
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('get_score_repeat/<sheet_id>/', methods=['GET'])
def get_score_repeat(sheet_id):
    try:
        res = AnsweringScoringController().get_score(
            answer_sheet_id=sheet_id,
            re_score=True
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


@bp.route('error_report/<question_id>/', methods=['POST'])
def error_report(question_id):
    args = request.json
    text = args.get('text')
    try:
        res = QuestionController().question_error_feedback(
            question_id=question_id,
            text=text
        )
        if res[0]:
            return SuccessDataResponse(res[1])
        else:
            return ArgumentExceptionResponse(msg=f'{res[1]}')
    except Exception as e:
        return ArgumentExceptionResponse(msg=f'{e}')


# heart beat
@bp.route('test_hb', methods=['GET'])
def test_hb():
    return SuccessDataResponse([])
