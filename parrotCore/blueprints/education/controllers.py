from datetime import datetime, timezone, timedelta, date
from blueprints.account.models import Accounts, Users
from blueprints.education.models import (
    Exams,
    Subjects,
    Scores,
    ScoreRubric,
    Patterns,
    Sections,
    Resources,
    QuestionsType,
    BasicQuestionsType,
    IndicatorQuestion,
    Indicators,
    Questions,
    Submissions,
    AnswerSheetRecord,
    VocabBase,
    VocabCategoryRelationships,
    VocabCategorySimilarities
)
from blueprints.grading.grading_func import Grading
import pprint
from utils.structure import Tree, TreeNode
from utils.redis_tools import RedisWrapper
from configs.environment import DATABASE_SELECTION
from configs.operation import NON_MEMBER_MODEL_AMOUNT
from sqlalchemy import select, and_, or_, join, outerjoin, update, insert, delete, text, asc
import time
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import bindparam
from itertools import groupby
from operator import itemgetter
import random
import asyncio

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s
import json

logger = get_general_logger('education', path=abspath('logs', 'core_web'))


class QuestionController(crudController):
    """
    事务模块 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有事务表单(Projects, 问卷s, Sections, Resources)
    init: 先创建Projects => 问卷s => Sections, Resources
    """

    def question_error_feedback(self, question_id, text):
        update_s = {
            "id": question_id,
            "error_feedback": text
        }
        res, data = self._update(model=Questions, update_parameters=update_s, restrict_field="id")
        return res, data

    @staticmethod
    def select_records(group_, number):
        sorted_group = sorted(group_, key=lambda x: x['order'], reverse=True)
        top_two = sorted_group[:2]
        rest = sorted_group[2:]
        random_selection = random.sample(rest, min(len(rest), number - 2)) if len(rest) > number - 2 else rest
        sorted_group = sorted(top_two + random_selection, key=lambda x: x['order'])
        return sorted_group

    def _get_all_questions_under_section(self, section_id, active=None):
        with db_session('core') as session:
            section = self._retrieve(model=Sections, restrict_field='id', restrict_value=section_id)
            if section:
                if active:
                    questions = (
                        session.query(Questions)
                        .filter(Questions.section_id == section_id)
                        .all()
                    )
                    return s.serialize_list(questions, self.default_not_show)
                else:
                    questions = (
                        session.query(Questions)
                        .filter(Questions.section_id == section_id)
                        .filter(Questions.is_active == active)
                        .all()
                    )
                    return s.serialize_list(questions, self.default_not_show)
            else:
                return 'Invalid Section Id'

    @staticmethod
    def fetch_questions(question_ids, session, ac_type, fetch_question=None):
        # -------------------- get all questions joined with question type ---------------------#
        subquery = select([
            Questions.id.label('id'),
            Questions.question_title,
            Questions.question_content,
            Questions.question_stem,
            Questions.question_type,
            Questions.keywords,
            Questions.stem_weights,
            Questions.has_ans,
            Questions.voice_link,
            Questions.voice_content,
            Questions.max_score,
            Questions.order,
            Questions.d_level,
            Questions.father_question,
            Questions.section_id,
            QuestionsType.id.label('question_type_id'),
            QuestionsType.type_name,
            QuestionsType.basic_question_type.label('b_question_type_id'),
            QuestionsType.detail.label('q_detail'),
            QuestionsType.restriction.label('q_restriction'),
            QuestionsType.rubric
        ]).select_from(
            Questions
        ).outerjoin(
            QuestionsType, Questions.question_type == QuestionsType.id
        ).where(
            Questions.id.in_(question_ids)
        ).subquery('Q')

        # Final query joining the subquery with BasicQuestionsType
        final_query = select([
            subquery,
            BasicQuestionsType.detail,
            BasicQuestionsType.restriction,
            BasicQuestionsType.cal_function,
            BasicQuestionsType.type_name
        ]).select_from(
            subquery
        ).outerjoin(
            BasicQuestionsType, subquery.c.b_question_type_id == BasicQuestionsType.id
        )
        results = session.execute(final_query).fetchall()

        # -------------------------------------- 解析 ----------------------------------------#
        start = time.time()
        refine_questions = []
        root_questions = []
        redis_store = {}
        sections = {}
        for result in results:
            if not result.has_ans:
                record = {
                    "question_id": result.id,
                    "section_id": result.section_id,
                    "question_title": result.question_title,
                    "question_content": result.question_content,
                    "question_type": result.type_name,
                    "question_stem": result.question_stem,
                    "voice_link": result.voice_link,
                    "voice_content": result.voice_content,
                    "max_score": result.max_score,
                    "father_id": result.father_question,
                    "question_depth": result.d_level,
                    "keywords": json.loads(result.keywords) if result.keywords else None,
                    "order": result.order
                }

                if result.father_question == -1:
                    root_questions.append(record)
                else:
                    refine_questions.append(record)

                # redis_store[result.id] = record

            else:
                try:
                    if result.question_stem:
                        merged_detail = {**json.loads(result.detail), **json.loads(result.q_detail),
                                         'd': result.question_stem.split(";")}
                    else:
                        merged_detail = {**json.loads(result.detail), **json.loads(result.q_detail),
                                         'd': []}
                except:
                    merged_detail = {}

                try:
                    if not result.q_restriction:
                        merged_restrict = json.loads(result.restriction)
                    else:
                        merged_restrict = {**json.loads(result.restriction), **json.loads(result.q_restriction)}
                except:
                    merged_restrict = {}

                if result.keywords:
                    k = json.loads(result.keywords)
                else:
                    k = {}

                account_ans, duration, answer_voice_link, model_answer, answer_video_link, upload_file_link = None, None, None, None, None, None
                if ac_type == 'create':
                    if result.stem_weights:
                        account_ans = [0] * len([int(num) for num in result.stem_weights.split(";")])
                        duration = None
                    else:
                        if result.question_stem and len(result.question_stem.split(";")) > 1:
                            account_ans = [0] * len(result.question_stem.split(";"))
                        else:
                            account_ans = ''
                        duration = None
                elif ac_type == 'get':
                    if fetch_question[result.id]['a']:
                        try:
                            account_ans = [int(num) for num in fetch_question[result.id]['a'].split(";")]
                        except:
                            account_ans = fetch_question[result.id]['a']
                    else:
                        account_ans = fetch_question[result.id]['a']

                    duration = fetch_question[result.id]['d']
                    model_answer = fetch_question[result.id]['m']
                    answer_voice_link = fetch_question[result.id]['voice']
                    answer_video_link = fetch_question[result.id]['video']
                    upload_file_link = fetch_question[result.id]['f']

                if result.section_id and result.section_id not in sections:
                    sections[result.section_id] = 1

                record = {
                    "question_id": result.id,
                    "question_title": result.question_title,
                    "question_content": result.question_content,
                    "question_type": result.type_name,
                    "section_id": result.section_id,
                    "question_depth": result.d_level,
                    "father_id": result.father_question,
                    "max_score": result.max_score,
                    "voice_link": result.voice_link,
                    "voice_content": result.voice_content,
                    "keywords": k,
                    "order": result.order,
                    "answer": account_ans,
                    "duration": duration,
                }
                # not required, to save more space
                fields = [
                    ("restriction", merged_restrict),
                    ("detail", merged_detail['d'] if 'd' in merged_detail else None),
                    ("options_label", merged_detail['ol'] if 'ol' in merged_detail else None),
                    ("answer_weight",
                     [int(num) for num in result.stem_weights.split(";")] if result.stem_weights else None),
                    ("model_answer", model_answer if model_answer else None),
                    ("answer_voice_link", answer_voice_link if answer_voice_link else None),
                    ("answer_video_link", answer_video_link if answer_video_link else None),
                    ("upload_file_link", upload_file_link if upload_file_link else None),
                ]
                for key, value in fields:
                    if value is not None:
                        record[key] = value

                if ac_type == 'get':
                    record['score'] = fetch_question[result.id]['s']

                if result.father_question == -1:
                    root_questions.append(record)
                else:
                    refine_questions.append(record)

                # redis_store[result.id] = record

        # --------- 跟section的题目进行比对，检查是否有过多题目，如果多于section的题目数，随机抽取 ---- #
        for key in sections.keys():
            r = (
                session.query(Sections)
                .filter(Sections.id == key)
                .one_or_none()
            )
            if r:
                sections[key] = r.no_questions

        refine_questions.sort(key=lambda x: x['section_id'])
        # Group by 'section_id' and process each group
        grouped_records = groupby(refine_questions, key=itemgetter('section_id'))
        selected_records = []

        for section_id, group in grouped_records:
            group_l = list(group).copy()
            num = len(group_l)
            if section_id:
                if num <= sections[section_id]:
                    selected_records.extend(group_l)
                else:
                    selected_records.extend(QuestionController().select_records(group_l, sections[section_id]))
            else:
                selected_records.extend(group_l)

        del refine_questions  # free the space

        # # --------   make a tree structure for front end -------- #
        tree = Tree()
        for question in root_questions:
            tree.add_root(question)
            redis_store[question['question_id']] = question
        for question in selected_records:
            redis_store[question['question_id']] = question
            tree.add_node("question_id", question["father_id"], question)

        res_questions = tree.print_tree()
        return res_questions, redis_store, list(sections.keys())


class AnsweringScoringController(crudController):
    def create_mock_answer_sheet(self, account_id=None, type='mock_exam'):
        if account_id is None:
            return False, "未知账户"

        new_answer_sheet = {
            "account_id": account_id,
            "status": 1,
            "type": type,
            "max_score": 0,
            "is_time": True,
            "father_sheet": -1,
            "is_check_answer": False,
            "is_active": 1,
            "is_graded": 0
        }
        create_new = self._create(model=AnswerSheetRecord, create_params=new_answer_sheet)

        if not create_new[0]:
            return False, create_new[1]

        sheet_id = create_new[1]
        response = {
            "sheet_id": sheet_id,
            "is_time": True,
            "is_check_answer": False,
            "children_sheets": []
        }
        return True, response

    def get_mock_answer_sheet(self, sheet_id, contin=False):
        with db_session('core') as session:
            record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.id == sheet_id)
                .one_or_none()
            )

            if not record:
                return False, '找不到答题卡'

            children_record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.father_sheet == sheet_id)
                .all()
            )
            children_sheets = []

            success = True
            for _record in children_record:
                resp, data = self.get_test_answers(_record.id, contin=contin)
                if not resp:
                    success = False
                    break
                else:
                    children_sheets.append(data)

            if not success:
                children_sheets = []

            response = {
                "sheet_id": record.id,
                "is_time": record.is_time,
                "is_check_answer": record.is_check_answer,
                "count": len(children_record),
                "children_sheets": children_sheets
            }

            return True, response

    def create_answer_sheet(self, account_id=None, type='practice', question_ids=None, father_sheet=None):
        if account_id:
            # 查找exam_ids下面所有的sections_id
            with db_session('core') as session:
                if question_ids:
                    questions = (
                        session.query(Questions)
                        .filter(Questions.id.in_(question_ids))
                        .filter(Questions.is_active.is_(True))
                        .all()
                    )
                    total_max = sum([x.max_score for x in questions])
                    section_ids = {}
                    for q in questions:
                        if q.section_id not in section_ids:
                            section_ids[q.section_id] = 1
                    sections_ = (
                        session.query(Sections)
                        .filter(Sections.id.in_(section_ids.keys()))
                        .filter(Sections.is_active.is_(True))
                        .all()
                    )

                    test_duration = sum([x.duration for x in sections_]) * 60
                    # -------------------- get all questions id under the root ids ---------------------#
                    base_query = select([
                        Questions.id,
                        Questions.father_question
                    ]).where(Questions.id.in_(question_ids))
                    # Define the CTE expression.
                    question_hierarchy = base_query.cte(name='QuestionHierarchy', recursive=True)
                    # Define the alias for the CTE and the Questions table for the recursive part.
                    question_hierarchy_alias = aliased(question_hierarchy, name='qh')
                    questions_alias = aliased(Questions, name='q')

                    # Add the recursive part to the CTE.
                    question_hierarchy = question_hierarchy.union_all(
                        select([
                            questions_alias.id,
                            questions_alias.father_question
                        ]).where(questions_alias.father_question == question_hierarchy_alias.c.id)
                    )
                    # Execute the query.
                    questions = session.execute(select([question_hierarchy])).fetchall()
                    all_ids = [x.id for x in questions]

                    res_questions, redis_store, _sections = QuestionController().fetch_questions(
                        question_ids=all_ids,
                        session=session,
                        ac_type="create"
                    )
                    # ------------------------------------create answer sheet---------------------------#
                    if not type == 'mock_exam':
                        is_time, is_check_answer = 0, 1
                    else:
                        is_time, is_check_answer = 1, 0
                    new_answer_sheet = {
                        "account_id": account_id,
                        "status": 1,
                        "type": type,
                        "father_sheet": father_sheet if father_sheet is not None else -1,
                        "max_score": total_max,
                        "is_time": is_time,
                        "is_check_answer": is_check_answer,
                        "is_active": 1,
                        "is_graded": 0
                    }
                    create_new = self._create(model=AnswerSheetRecord, create_params=new_answer_sheet)

                    if create_new[0]:
                        sheet_id = create_new[1]
                        response = {
                            "sheet_id": sheet_id,
                            "is_time": is_time,
                            "is_check_answer": is_check_answer,
                            "time_remain": test_duration,
                            "max_score": total_max,
                            "type": type,
                            "questions": res_questions
                        }

                        # store question submission to redis
                        redis_dic = {
                            "sheet_id": sheet_id,
                            "is_time": is_time,
                            "is_check_answer": is_check_answer,
                            "time_remain": test_duration,
                            "max_score": total_max,
                            "type": type,
                            "questions": redis_store
                        }
                        redis_cli = RedisWrapper('core_cache')
                        redis_cli.set(f'Sheet-{sheet_id}', redis_dic)

                        # 开始计时
                        s_l = []
                        for section in _sections:
                            new_record = {
                                "answer_sheet_id": sheet_id,
                                "section_id": section,
                                'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                            }
                            s_l.append(new_record)

                        session.execute(
                            insert(Scores),
                            s_l
                        )

                        default_dic = {
                            'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}

                        update_time = {
                            "id": sheet_id,
                            "start_time": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            "end_time": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))) + timedelta(
                                seconds=test_duration + 2)
                            # 2 seconds grace period
                        }

                        records = (
                            session.query(AnswerSheetRecord)
                            .filter(getattr(AnswerSheetRecord, "id") == update_time["id"])
                            .update({**update_time, **default_dic})
                        )
                        try:
                            session.commit()
                            session.close()
                            return True, response
                        except:
                            session.rollback()
                            session.close()
                            return False, "创建答卷失败"

                    else:
                        session.close()
                        return False, "创建答卷失败"
        else:
            return False, "未知账户"

    def get_test_answers_history(self, account_id):
        # 获取问卷答题信息，
        # status = 0为已完成答题，批改问卷
        # status = 1为正在答题
        # status = 2为答题暂停
        # status = 3为已完成答题，题目已保存，未批改
        # status = 4为正在批改
        with db_session('core') as session:
            records = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.account_id == account_id)
                .all()
            )
            return s.serialize_list(records)

    def get_test_answers(self, sheet_id, contin=False, redo=False):
        # 获取问卷答题信息，
        # status = 0为已完成答题，批改问卷
        # status = 1为正在答题
        # status = 2为答题暂停
        # status = 3为已完成答题，题目已保存，未批改
        # status = 4为正在批改
        # status = 5为批改完成，未录入分数
        with db_session('core') as session:
            start = time.time()
            record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.id == sheet_id)
                .one_or_none()
            )
            if record:
                if record.status == 1:
                    response = {
                        "sheet_id": sheet_id,
                        "is_time": record.is_time,
                        "is_check_answer": record.is_check_answer,
                        "time_remain": (record.end_time.replace(tzinfo=timezone(timedelta(hours=8))) - datetime.now(
                            timezone.utc).astimezone(
                            timezone(timedelta(hours=8)))).total_seconds() if record.end_time is not None else None,
                        "max_score": record.max_score,
                        "score": record.score if record.score else None,
                        "type": record.type.value,
                    }
                    redis_cli = RedisWrapper('core_cache')
                    cache_dict = redis_cli.get(f'Sheet-{sheet_id}')
                    if cache_dict:
                        cache_question = cache_dict['questions']
                        refine_questions = [x for x in cache_question.values() if x['father_id'] != -1]
                        root_questions = [x for x in cache_question.values() if x['father_id'] == -1]

                        tree = Tree()
                        for question in root_questions:
                            tree.add_root(question)
                        for question in refine_questions:
                            tree.add_node("question_id", question["father_id"], question)

                        res_questions = tree.print_tree()
                        response['questions'] = res_questions
                        return True, response

                    else:
                        # 没有迁移至数据库
                        return False, "无法找到题目缓存"
                else:
                    start = time.time()
                    redis_cli = RedisWrapper('core_cache')
                    cache_dict = redis_cli.get(f'Sheet-non-{sheet_id}')
                    response = {
                        "sheet_id": sheet_id,
                        "is_time": record.is_time,
                        "is_check_answer": record.is_check_answer,
                        "time_remain":
                            (record.end_time - record.last_pause_time).total_seconds() if record.status == 2 else 0,
                        "max_score": record.max_score,
                        "score": record.score if record.score else None,
                        "type": record.type.value,
                    }

                    # 如若有缓存
                    if cache_dict:
                        cache_question = cache_dict['questions']
                        refine_questions = [x for x in cache_question.values() if x['father_id'] != -1]
                        root_questions = [x for x in cache_question.values() if x['father_id'] == -1]

                        tree = Tree()
                        for question in root_questions:
                            tree.add_root(question)
                        for question in refine_questions:
                            tree.add_node("question_id", question["father_id"], question)
                        res_questions = tree.print_tree()
                        response['questions'] = res_questions
                        return True, response
                    else:
                        questions = (
                            session.query(Submissions)
                            .filter(Submissions.answer_sheet_id == sheet_id)
                            .all()
                        )
                        question_ids = []
                        question_dic = {}

                        for each in questions:
                            question_ids.append(each.question_id)
                            question_dic[each.question_id] = {}
                            if each.answer is not None:
                                question_dic[each.question_id]['a'] = each.answer
                            else:
                                question_dic[each.question_id]['a'] = None
                            if each.duration is not None:
                                question_dic[each.question_id]['d'] = each.duration
                            else:
                                question_dic[each.question_id]['d'] = None
                            if each.score is not None:
                                question_dic[each.question_id]['s'] = each.score
                            else:
                                question_dic[each.question_id]['s'] = None

                            if each.video_link is not None:
                                question_dic[each.question_id]['video'] = each.video_link
                            else:
                                question_dic[each.question_id]['video'] = None

                            if each.upload_file_link is not None:
                                question_dic[each.question_id]['f'] = each.upload_file_link
                            else:
                                question_dic[each.question_id]['f'] = None

                            if each.model_answer is not None:
                                question_dic[each.question_id]['m'] = each.model_answer
                            else:
                                question_dic[each.question_id]['m'] = None

                            if each.voice_link is not None:
                                question_dic[each.question_id]['voice'] = each.voice_link
                            else:
                                question_dic[each.question_id]['voice'] = None

                        res_questions, redis_store, sections = QuestionController().fetch_questions(
                            question_ids=question_ids,
                            session=session,
                            ac_type="get",
                            fetch_question=question_dic)

                        test_remain = (
                                record.end_time - record.last_pause_time).total_seconds() if record.status == 2 else 0
                        redis_dic = {
                            "sheet_id": sheet_id,
                            "is_time": record.is_time,
                            "is_check_answer": record.is_check_answer,
                            "time_remain": test_remain,
                            "max_score": record.max_score,
                            "score": record.score if record.score else None,
                            "type": record.type.value,
                            "questions": redis_store
                        }
                        response['questions'] = res_questions
                        redis_cli = RedisWrapper('core_cache')
                        if not redo and redis_dic['score'] is not None:
                            redis_cli.set(f'Sheet-non-{sheet_id}', redis_dic, ex=600)

                        if contin:
                            try:
                                if record.status != 2:
                                    return False, "该前单题卡状态不支持继续"

                                update_s = {
                                    "id": sheet_id,
                                    "status": 1,
                                    "end_time": datetime.now(timezone.utc).astimezone(
                                        timezone(timedelta(hours=8))) + timedelta(seconds=test_remain + 2)
                                }
                                self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                                redis_cli.set(f'Sheet-{sheet_id}', redis_dic)
                                session.commit()
                            except Exception as e:
                                session.rollback()
                                return False, str(e)
                        return True, response
            else:
                return False, "未找到答卷"

    def update_question_answer(self, sheet_id, question_id, duration=None, answer=None, answer_voice_link=None,
                               answer_video_link=None, upload_file_link=None, model_answer=None, score=None):
        redis_cli = RedisWrapper('core_cache')
        cache_dict = redis_cli.get(f'Sheet-{sheet_id}')
        if cache_dict:
            if answer is not None:
                cache_dict['questions'][str(question_id)][
                    'answer'] = answer  # Replace 'new_value' with the desired value
            if answer_voice_link is not None:
                cache_dict['questions'][str(question_id)]['answer_voice_link'] = answer_voice_link
            if answer_video_link is not None:
                cache_dict['questions'][str(question_id)]['answer_video_link'] = answer_video_link
            if upload_file_link is not None:
                cache_dict['questions'][str(question_id)]['upload_file_link'] = upload_file_link
            if model_answer is not None:
                cache_dict['questions'][str(question_id)]['model_answer'] = model_answer
            if duration is not None:
                cache_dict['questions'][str(question_id)]['duration'] = duration
            # 支持中途算分
            if score is not None:
                cache_dict['questions'][str(question_id)]['score'] = score

            redis_cli.set(f'Sheet-{sheet_id}', cache_dict)
            return True, "OK."
        else:
            return False, "未找到答卷题目缓存"

    def get_sheet_status(self, sheet_id):
        # 答卷当中获取当前答题状态
        redis_cli = RedisWrapper('core_cache')
        cache_dict = redis_cli.get(f'Sheet-{sheet_id}')
        if cache_dict:
            questions_dic = cache_dict['questions']
            questions_li = []
            for value in questions_dic.values():
                if 'answer' in value:
                    if type(value['answer']) == list:
                        if value['answer'] != [0] * len(value['answer']):
                            value['is_answer'] = True
                        else:
                            value['is_answer'] = False
                    else:
                        if type(value['answer']) == str:
                            value['is_answer'] = True
                        else:
                            value['is_answer'] = False
                    questions_li.append(value)
            return True, questions_li
        else:
            return False, "未找到答卷题目缓存"

    def pause_sheet(self, sheet_id):
        with db_session('core') as session:
            children_record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.father_sheet == sheet_id)
                .order_by(asc(AnswerSheetRecord.create_time))
                .all()
            )

            # 给所有的children打分
            try:
                if len(children_record) > 0:
                    for record in children_record:
                        self.save_answer(sheet_id=record.id)
                        update_s = {
                            "id": record.id,
                            "status": 2,
                            'last_pause_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                        }
                        self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                else:
                    self.save_answer(sheet_id)

                update_s = {
                    "id": sheet_id,
                    "status": 2,
                    'last_pause_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                }
                self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                session.commit()
                return True, "暂停成功"
            except Exception as e:
                session.rollback()
                return False, str(e)

    def save_answer(self, sheet_id):
        redis_cli = RedisWrapper('core_cache')
        cache_dict = redis_cli.get(f'Sheet-{sheet_id}')
        if cache_dict:
            questions_dic = cache_dict['questions']
            with db_session('core') as session:
                for value in questions_dic.values():
                    single_answer = None
                    if 'answer' in value and value['answer']:
                        if type(value['answer']) == list:
                            single_answer = ';'.join(map(str, value['answer']))
                        elif type(value['answer']) == str:
                            single_answer = value['answer']
                    elif 'answer' in value and not value['answer']:
                        single_answer = value['answer']
                    else:
                        single_answer = None

                    answer = {
                        'question_id': value['question_id'],
                        'answer': single_answer,
                        'stem_weight': ';'.join(map(str, value['answer_weight'])) if 'answer_weight' in value and value[
                            'answer_weight'] else None,
                        'duration': value['duration'] if 'duration' in value else None,
                        'voice_link': value['answer_voice_link'] if 'answer_voice_link' in value else None,
                        'video_link': value['answer_video_link'] if 'answer_video_link' in value else None,
                        'model_answer': value['model_answer'] if 'model_answer' in value else None,
                        'upload_file_link': value['upload_file_link'] if 'upload_file_link' in value else None,
                        'score': value['score'] if 'score' in value else None,
                        'answer_sheet_id': sheet_id,
                        'max_score': value['max_score'],
                        'is_graded': False,
                        'submit_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                    }
                    default_dic = {
                        'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                        'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                    }
                    merged_dict = {**default_dic, **answer}
                    record = Submissions(**merged_dict)
                    session.add(record)

                try:
                    update_s = {
                        "id": sheet_id,
                        "status": 3
                    }
                    self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                    session.commit()
                except Exception as e:
                    session.rollback()
                    return False, str(e)
            if redis_cli.delete(f'Sheet-{sheet_id}') == 1:
                return True, "题目数据保存成功"
            else:
                return False, "题目保存成功，缓存删除失败"
        else:
            return False, "无法找到题目缓存"

    def get_score(self, answer_sheet_id, re_score=False):
        with db_session('core') as session:
            answer_record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.id == answer_sheet_id)
                .one_or_none()
            )
            if answer_record:
                children_record = (
                    session.query(AnswerSheetRecord)
                    .filter(AnswerSheetRecord.father_sheet == answer_sheet_id)
                    .order_by(asc(AnswerSheetRecord.create_time))
                    .all()
                )

                # 给所有的children打分
                if len(children_record) > 0 or answer_record.end_time is None:
                    max_score = 0
                    score = 0
                    success = True

                    detail = []
                    for record in children_record:
                        if record.score is not None:
                            score += record.score
                        else:
                            success = False
                        if record.max_score is not None:
                            max_score += record.max_score

                        _record = {
                            "sheet_id": record.id,
                            "max_score": record.max_score,
                            "score": record.score
                        }
                        detail.append(_record)

                    rs = {
                        "sheet_id": answer_record.id,
                        "is_time": answer_record.is_time,
                        "is_check_answer": answer_record.is_check_answer,
                        "max_score": max_score if success else None,
                        "score": score if success else None,
                        "detail": detail,
                        "type": answer_record.type.value
                    }
                    update_s = {
                        "id": answer_sheet_id,
                        "is_graded": 1,
                        "status": 0,
                    }
                    self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                    return True, rs

                if answer_record.status == 0:
                    l = s.serialize_dic(answer_record, self.default_not_show)
                    l['type'] = l['type'].value

                    # 获取小分
                    res, data = self.get_score_question_detail(answer_sheet_id=answer_sheet_id, session=session)
                    if not res:
                        return False, data

                    # 获取 tag 分数
                    res_tag, data_tag = self.get_indicators_detail(answer_sheet_id=answer_sheet_id, session=session)
                    if not res_tag:
                        return False, data_tag

                    resp, questions = self.get_test_answers(sheet_id=answer_sheet_id, redo=re_score)

                    if resp:
                        l["questions_r"] = questions
                        l["score_d"] = data
                        l["tag_d"] = data_tag
                        return True, l
                    else:
                        return False, "未找到打分试卷"
                elif (answer_record.status == 5 and answer_record.is_graded == 1) or re_score:  # 完成批改但未登分
                    records = (
                        session.query(Scores)
                        .filter(Scores.answer_sheet_id == answer_sheet_id)
                        .all()
                    )
                    t_score = 0
                    for record in records:
                        if record.score is None:
                            t_score = record.score
                            break
                        else:
                            t_score += record.score

                    update_s = {
                        "id": answer_sheet_id,
                        "score": t_score,
                        "status": 0,
                    }
                    self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                    re_s = s.serialize_dic(answer_record, self.default_not_show)

                    # 获取小分
                    res, data = self.get_score_question_detail(answer_sheet_id=answer_sheet_id, session=session)
                    if not res:
                        return False, data

                    # 获取 tag 分数
                    res_tag, data_tag = self.get_indicators_detail(answer_sheet_id=answer_sheet_id, session=session)
                    if not res_tag:
                        return False, data_tag

                    # 生成答案:

                    re_s['score'] = t_score
                    re_s['type'] = re_s['type'].value
                    re_s["status"] = 0
                    resp, questions = self.get_test_answers(sheet_id=answer_sheet_id, redo=re_score)
                    if resp:
                        re_s["questions_r"] = questions
                        re_s["score_d"] = data
                        re_s["tag_d"] = data_tag
                    else:
                        return False, '未找到打分试卷'

                    try:
                        session.commit()
                        # session.close()
                        return True, re_s
                    except Exception as e:
                        session.rollback()
                        # session.close()
                        return False, "获取失败"

                else:
                    return True, "未进入打分阶段/打分未完成"

            else:
                return False, "未查询到考卷信息"

    def model_scoring(self, sheet_id, question_id):
        # search for pattern
        logger.info(f"Sheet:{sheet_id}-Question:{question_id} - 开始模型打分任务")
        import requests
        with db_session('core') as session:
            redis = RedisWrapper("core_cache")
            record = (
                session.query(
                    Patterns.id,
                    Patterns.pattern_name,
                    Patterns.pattern_eng_name
                )
                .join(Sections, Patterns.id == Sections.pattern_id)
                .join(Questions, Sections.id == Questions.section_id)
                .filter(Questions.id == question_id)
                .one_or_none()
            )
            if not record:
                return False, ""

            account = (
                session.query(
                    Users.id,
                    Accounts.id.label('account_id'),
                    Accounts.model_today_used,
                    Users.user_plan
                )
                .join(AnswerSheetRecord, AnswerSheetRecord.account_id == Accounts.id)
                .join(Users, Users.id == Accounts.user_id)
                .filter(AnswerSheetRecord.id == sheet_id)
                .one_or_none()
            )
            if not account:
                return False, ""

            score, model_answer = 0, "{}"
            contine_fetch = True

            if account.user_plan == 0 or account.user_plan is None:
                if account.model_today_used >= NON_MEMBER_MODEL_AMOUNT:
                    model_answer = '{"msg":"用量已超使用上限制"}'
                    contine_fetch = False

            if contine_fetch:
                # 查看sheet状态：
                redis.set(f"InGrading-{sheet_id}-{question_id}", 1)
                redis.set(f"InGrading-{sheet_id}", 1)
                cache_dict = redis.get(f"Sheet-{sheet_id}")
                # 直接取
                if cache_dict:
                    answer_voice_link = cache_dict['questions'][str(question_id)][
                        'answer_voice_link'] if 'answer_voice_link' in cache_dict['questions'][
                        str(question_id)] else None
                    answer = cache_dict['questions'][str(question_id)]['answer']
                else:
                    # 取数据库
                    sub_record = (
                        session.query(Submissions)
                        .filter(and_(Submissions.question_id == question_id,
                                     Submissions.answer_sheet_id == sheet_id))
                        .one_or_none()
                    )
                    if sub_record:
                        answer_voice_link = sub_record.voice_link
                        answer = sub_record.answer

                q_record = (
                    session.query(
                        Questions.id,
                        Questions.voice_content,
                        Questions.question_content,
                        Questions.question_title,
                        Questions.section_id
                    )
                    .filter(Questions.id == question_id)
                    .one_or_none()
                )
                if record.pattern_eng_name == "Speaking":  # speaking model
                    try:
                        url = f"http://{'18.136.105.171'}:{57875}/v1/modelapi/speaking/gradeSpeaking/"
                        prompt = f"""Prompt: {q_record.question_title}"""
                        if q_record.voice_content:
                            prompt += f"""Source: {q_record.question_content}; {q_record.voice_content}"""

                        logger.info(f"Sheet:{sheet_id}-Question:{question_id} 开始访问speaking模型")
                        r = requests.post(url, json={
                            "prompt": prompt,
                            "audioLink": answer_voice_link,
                            "gradeType": "Independent Speaking"
                        }, timeout=600)

                        if r.json()['code'] == 10000:
                            res_data = r.json()['data']
                            score = res_data.get("Overall")
                            if score:
                                score = float(score)
                            model_answer = json.dumps(res_data)
                            update = (
                                session.query(Accounts)
                                .filter(Accounts.id == account.account_id)
                                .update({
                                    Accounts.model_today_used: account.model_today_used + 1
                                }))
                            logger.info(f"Sheet:{sheet_id}-Question:{question_id} speaking响应成功..")

                        else:
                            score = None
                            model_answer = '{"msg":"访问AI模型失败"}'
                            logger.info(
                                f"Sheet:{sheet_id}-Question:{question_id} speaking响应失败：不是成功code: {r.json()['code']}:{r.json()['msg']}（gpt出错）")

                    except Exception as e:
                        score = None
                        model_answer = f'{"msg":"访问AI模型失败:{str(e)}"}'

                elif record.pattern_eng_name == "Writing":  # writing model
                    try:
                        url = f"http://{'18.136.105.171'}:{57875}/v1/modelapi/writing/gradeWriting/"
                        prompt = f"""Prompt: {q_record.question_title} {q_record.question_content}\n"""
                        if q_record.voice_content:
                            prompt += f"""Source: {q_record.voice_content}"""

                        logger.info(f"Sheet:{sheet_id}-Question:{question_id} 开始访问writing模型")
                        r = requests.post(url, json={
                            "prompt": prompt,
                            "content": answer,
                            "gradeType": "Academic Discussion" if q_record.section_id == 12 else "Integrated Writing"
                        }, timeout=600)

                        if r.json()['code'] == 10000:
                            res_data = r.json()['data']
                            score = res_data.get("Overall")
                            if score:
                                score = float(score)
                            model_answer = json.dumps(res_data)
                            update = (
                                session.query(Accounts)
                                .filter(Accounts.id == account.account_id)
                                .update({
                                    Accounts.model_today_used: account.model_today_used + 1
                                }))
                            logger.info(f"Sheet:{sheet_id}-Question:{question_id} writing 响应成功..")
                        else:
                            score = None
                            model_answer = '{"msg":"访问AI模型失败"}'
                            logger.info(
                                f"Sheet:{sheet_id}-Question:{question_id} writing 响应失败：不是成功code: {r.json()['code']}:{r.json()['msg']}（gpt出错）")

                    except Exception as e:
                        score = None
                        model_answer = f'{"msg":"访问AI模型失败:{str(e)}"}'
                else:
                    score = None
                    model_answer = '{"msg":"AI模型批改未开放"}'

            # 超存结果
            cache_dict = redis.get(f"Sheet-{sheet_id}")
            redis.delete(f"InGrading-{sheet_id}-{question_id}")
            redis.delete(f"InGrading-{sheet_id}")
            if not cache_dict:
                update = (
                    session.query(Submissions)
                    .filter(and_(Submissions.question_id == question_id,
                                 Submissions.answer_sheet_id == sheet_id))
                    .update({
                        Submissions.last_update_time: datetime.now(timezone.utc).astimezone(
                            timezone(timedelta(hours=8))),
                        Submissions.score: score,
                        Submissions.model_answer: model_answer
                    })
                )

            else:
                # update_:
                self.update_question_answer(
                    sheet_id=sheet_id,
                    question_id=question_id,
                    model_answer=model_answer,
                    score=score
                )
                return True, score

            try:
                session.commit()
                return True, score
            except Exception as e:
                session.rollback()
                return False, 0

    def scoring(self, sheet_id, re_score=False):
        with db_session('core') as session:
            record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.id == sheet_id)
                .one_or_none()
            )
            if record:
                children_record = (
                    session.query(AnswerSheetRecord)
                    .filter(AnswerSheetRecord.father_sheet == sheet_id)
                    .all()
                )

                # 给所有的children打分
                if len(children_record) > 0 or record.end_time is None:
                    success = True
                    for c_record in children_record:
                        res, data = self.scoring(sheet_id=c_record.id, re_score=re_score)
                        if not res:
                            success = False
                            break

                    if not success:
                        return False, "打分失败"
                    else:
                        return True, "打分成功"

                if record.status == 1:
                    return False, "正在答题"

            update_s = {
                "id": sheet_id,
                "status": 4
            }
            self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")

            #  ----------------------------------开始打分------------------------------------------#
            # 把submission questions join 过来
            S = aliased(Submissions)
            Q = aliased(Questions)
            T = aliased(QuestionsType)
            BQT = aliased(BasicQuestionsType)

            # First subquery (L)
            subquery_l = select(
                S.id.label('submission_id'),
                S.question_id,
                S.answer,
                S.score,
                S.voice_link,
                S.video_link,
                S.upload_file_link,
                S.cal_method.label('cal_m'),
                S.max_score,
                S.model_answer,
                Q.stem_weights.label('question_stem'),
                Q.question_type,
                Q.correct_answer,
                Q.section_id,
                Q.cal_method.label('cal_m_q'),
                Q.is_cal,
                Q.has_ans,
                Q.father_question
            ).select_from(
                join(S, Q, S.question_id == Q.id)
            ).where(
                S.answer_sheet_id == sheet_id
            ).alias('L')

            # Second subquery (R)
            subquery_r = select(
                T.id,
                T.detail.label('q_detail'),
                T.restriction.label('q_restriction'),
                T.rubric.label('q_rubric'),
                BQT.restriction.label('restriction'),
                BQT.detail.label('detail'),
                BQT.cal_function.label('cal_m_B')
            ).select_from(
                join(T, BQT, T.basic_question_type == BQT.id)
            ).alias('R')

            # Final query
            final_query = select('*').select_from(
                outerjoin(subquery_l, subquery_r, subquery_l.c.question_type == subquery_r.c.id)
            )

            # Assuming you are using a session to query the database
            results = session.execute(final_query).fetchall()

            questions = []
            grading_instance = Grading()
            roots = []
            for result in results:
                if result.has_ans == 1:
                    # merged_detail = {**json.loads(result.detail), **json.loads(result.q_detail), 'd': result.question_stem.split(";")}
                    try:
                        if result.q_restriction:
                            merged_restrict = {**json.loads(result.restriction), **json.loads(result.q_restriction)}
                        else:
                            merged_restrict = json.loads(result.restriction)
                    except:
                        merged_restrict = {}

                    if result.answer:
                        try:
                            single_answer = [int(num) for num in result.answer.split(";")]
                        except:
                            single_answer = result.answer
                    else:
                        single_answer = None

                    question = {
                        'submission_id': result.submission_id,
                        'question_id': result.question_id,
                        'section_id': result.section_id,
                        'answer': single_answer,
                        'correct': [int(num) for num in
                                    result.correct_answer.split(";")] if result.correct_answer else None,
                        'weight': [int(num) for num in
                                   result.question_stem.split(";")] if result.question_stem else None,
                        'max_score': result.max_score,
                        'voice_link': result.voice_link,
                        'video_link': result.video_link,
                        'upload_file_link': result.upload_file_link,
                        'father_id': result.father_question,
                        'rubric': json.loads(result.q_rubric) if result.q_rubric else {},
                        # 'detail': merged_detail,
                        'restriction': merged_restrict,
                        'cal_method': result.cal_m,
                        'cal_fun': result.cal_m_B
                    }

                    # 自动计分
                    try:
                        if result.cal_m_q == 1:
                            if re_score:
                                score = getattr(grading_instance, question['cal_fun'])(
                                    answer=question['answer'],
                                    correct=question['correct'],
                                    weight=question['weight'],
                                    rubric=question['rubric'],
                                    restriction=question['restriction'],
                                    max_score=question['max_score']
                                )
                                question['score'] = score
                            else:
                                if result.score is None:
                                    score = getattr(grading_instance, question['cal_fun'])(
                                        answer=question['answer'],
                                        correct=question['correct'],
                                        weight=question['weight'],
                                        rubric=question['rubric'],
                                        restriction=question['restriction'],
                                        max_score=question['max_score']
                                    )
                                    question['score'] = score
                                else:
                                    question['score'] = result.score

                        else:
                            # 手动/模型 计分方法
                            if re_score:
                                score = getattr(grading_instance, question['cal_fun'])(
                                    sheet_id=sheet_id,
                                    question_id=question['question_id'],
                                    answer=question['answer'],
                                    voice_link=question['voice_link'],
                                    video_link=question['video_link'],
                                    upload_file_link=question['upload_file_link']
                                )
                                question['score'] = score
                            else:
                                if result.score is None:
                                    redis = RedisWrapper('core_cache')
                                    grading_record = redis.get(f"InGrading-{sheet_id}-{question['question_id']}")
                                    if grading_record:
                                        question['score'] = None
                                    else:
                                        score = getattr(grading_instance, question['cal_fun'])(
                                            sheet_id=sheet_id,
                                            question_id=question['question_id'],
                                            answer=question['answer'],
                                            voice_link=question['voice_link'],
                                            video_link=question['video_link'],
                                            upload_file_link=question['upload_file_link']
                                        )
                                        question['score'] = score
                                else:
                                    question['score'] = result.score
                    except Exception as e:
                        # 如果数据源问题道题出错，先默认为0，待修改后，可以重新计分
                        question['score'] = None

                    questions.append(question)

            from collections import defaultdict
            result = defaultdict(float)

            # 如果里面有任何一道题score为none，都记做计算总分失败
            whether_success = {}
            for d in questions:
                if d['score'] is None:
                    whether_success[d["section_id"]] = True

                result[d["section_id"]] += d["score"] if d['score'] else 0
            result_list = [{"section_id": section_id, "total_score": total_score} for section_id, total_score in
                           result.items()]
            u_r = []
            for d in result_list:
                if d['section_id']:
                    rubric = (
                        session.query(ScoreRubric)
                        .filter(ScoreRubric.section_id == d['section_id'])
                        .one_or_none()
                    )
                    if rubric:
                        s_r = {float(k): v for k, v in json.loads(rubric.rubric).items()}
                        max_score = rubric.max_score

                    record = (
                        session.query(Scores)
                        .filter(and_(Scores.answer_sheet_id == sheet_id, Scores.section_id == d['section_id']))
                        .one_or_none()
                    )

                    if record:
                        new_record = {
                            "s_id": record.id,
                            # "answer_sheet_id": answer_sheet_id,
                            # "section_id": d['section_id'] if d['section_id'] else None,
                            "total_score": d['total_score'],
                            "score": s_r[d['total_score']] if s_r else None,
                            "max_score": max_score if max_score else None,
                            "last_update_time": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                        }
                        # 需要每道题score都不为none才能计算总分 （口语、写作可能打分失败）
                        if d['section_id'] in whether_success:
                            new_record["total_score"] = None
                            new_record['score'] = None
                        u_r.append(new_record)
                else:
                    new_record = {
                        "answer_sheet_id": sheet_id,
                        "section_id": d['section_id'] if d['section_id'] else None,
                        "total_score": d['total_score'],
                        "score": s_r[d['total_score']] if s_r else None,
                        "max_score": max_score if max_score else None,
                        "last_update_time": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                    }
                    if 'w' in d:
                        new_record["total_score"] = None
                        new_record['score'] = None
                    u_r.append(new_record)

            # 更新成绩
            commit = []
            for question in questions:
                update_ = {
                    "s_id": question['submission_id'],
                    "is_graded": 1,
                    "score": question['score'],
                    "last_update_time": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                }
                commit.append(update_)

            session.execute(
                update(Scores).where(Scores.id == bindparam('s_id')).values(
                    total_score=bindparam('total_score'),
                    score=bindparam('score'),
                    max_score=bindparam('max_score'),
                    last_update_time=bindparam('last_update_time')
                ),
                u_r
            )

            session.execute(
                update(Submissions).where(Submissions.id == bindparam('s_id')).values(
                    is_graded=bindparam('is_graded'),
                    score=bindparam('score'),
                    last_update_time=bindparam('last_update_time')
                ),
                commit
            )

            try:
                update_s = {
                    "id": sheet_id,
                    "status": 5,
                    "is_graded": 1
                }
                self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                session.commit()
                session.close()
                return True, "完成打分"
            except Exception as e:
                update_s = {
                    "id": sheet_id,
                    "status": 3
                }
                self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                session.rollback()
                session.close()
                return False, str(e)

    def get_score_question_detail(self, answer_sheet_id, session):
        try:
            raw_sql = text(f"""
                SELECT
                Submissions.question_id,
                CASE WHEN Submissions.score = Submissions.max_score THEN 1 ELSE 0 END AS IsMaxScore,
                Q.father_question,
                Q.has_ans,
                Q.section_id,
                Q.remark
                FROM Submissions
                JOIN Questions Q ON Q.id = Submissions.question_id
                WHERE Submissions.answer_sheet_id = {answer_sheet_id}
                ORDER BY father_question ASC
                """)
            scores_d = session.execute(raw_sql).fetchall()

            q_s = {}
            father_q = {}
            remark = {}
            q = {}
            for score_d in scores_d:
                if score_d.father_question == -1:
                    if score_d.question_id not in father_q:
                        father_q[score_d.question_id] = 0
                        if score_d.has_ans == 0:
                            q[score_d.question_id] = 0
                        else:
                            q[score_d.question_id] = score_d.IsMaxScore
                        remark[score_d.question_id] = score_d.remark
                        if score_d.section_id not in q_s:
                            q_s[score_d.section_id] = [score_d.question_id]
                        else:
                            q_s[score_d.section_id].append(score_d.question_id)

                else:
                    if score_d.father_question in father_q:
                        father_q[score_d.father_question] += 1
                        q[score_d.father_question] += score_d.IsMaxScore

            res = {}
            for section in sorted(list(q_s.keys())):
                se = []
                for i in q_s[section]:
                    _q = {}
                    _q['name'] = remark[i]
                    _q['count'] = q[i]
                    _q['total'] = father_q[i]
                    se.append(_q)
                res[section] = se
            return True, res
        except Exception as e:
            return False, str(e)

    def get_indicators_detail(self, answer_sheet_id, session):
        """每篇Tag的分值，sql可以与get_score_question_detail合并，但考虑到业务上的更改，暂时做分开"""
        try:
            sec = {}
            raw_sql = text(f"""
            SELECT
                S.id,
                S.section_name
            FROM Submissions
            JOIN Questions Q ON Q.id = Submissions.question_id
            JOIN Sections S on Q.section_id = S.id
            WHERE Submissions.answer_sheet_id = {answer_sheet_id};   
            """)
            records = session.execute(raw_sql).fetchall()
            for record in records:
                if record.id not in sec:
                    sec[record.id] = record.section_name

            raw_sql = text(f"""
                WITH QUESTION_IN AS (
                    SELECT
                        Submissions.question_id,
                        CASE WHEN Submissions.score = Submissions.max_score THEN 1 ELSE 0 END AS IsMaxScore,
                        IQ.indicator_id,
                        I.indicator_name
                    FROM Submissions
                    JOIN Questions Q ON Q.id = Submissions.question_id
                    JOIN Indicators_Questions IQ on Q.id = IQ.question_id
                    JOIN Indicators I on IQ.indicator_id = I.id
                    WHERE Submissions.answer_sheet_id = {answer_sheet_id}
                    )
                    SELECT
                        SUM(QUESTION_IN.IsMaxScore) AS sum,
                        COUNT(QUESTION_IN.IsMaxScore) AS count,
                        QUESTION_IN.indicator_name AS name
                    FROM QUESTION_IN
                    GROUP BY QUESTION_IN.indicator_id
                """)
            scores_d = session.execute(raw_sql).fetchall()
            res = {}
            res["all"] = []
            for record in scores_d:
                e_ = {}
                e_['name'] = record.name
                e_['count'] = int(record.count)
                e_['sum'] = int(record.sum)
                res["all"].append(e_)

            count = 1
            for key in sec.keys():
                raw_sql = text(f"""
                WITH QUESTION_IN AS (
                    SELECT
                        Submissions.question_id,
                        CASE WHEN Submissions.score = Submissions.max_score THEN 1 ELSE 0 END AS IsMaxScore,
                        IQ.indicator_id,
                        I.indicator_name
                    FROM Submissions
                    JOIN Questions Q ON Q.id = Submissions.question_id
                    JOIN Sections S on Q.section_id = S.id
                    JOIN Indicators_Questions IQ on Q.id = IQ.question_id
                    JOIN Indicators I on IQ.indicator_id = I.id
                    WHERE Submissions.answer_sheet_id = {answer_sheet_id}
                    AND S.id = {key}
                )
                SELECT
                    SUM(QUESTION_IN.IsMaxScore) AS sum,
                    COUNT(QUESTION_IN.IsMaxScore) AS count,
                    QUESTION_IN.indicator_name AS name
                FROM QUESTION_IN
                GROUP BY QUESTION_IN.indicator_id
                """)
                sub_scores_d = session.execute(raw_sql).fetchall()
                res[str(count)] = []

                for record in sub_scores_d:
                    e_ = {}
                    e_['name'] = record.name
                    e_['count'] = int(record.count)
                    e_['sum'] = int(record.sum)
                    res[str(count)].append(e_)

                count += 1

            return True, res
        except Exception as e:
            return False, str(e)

class TransactionsController(crudController):
    """
    事务模块 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有事务表单(Projects, 问卷s, Sections, Resources)
    init: 先创建Projects => 问卷s => Sections, Resources
    """

    def get_recent_pattern_scores(self, account_id, offset):
        from configs.operation import LAST_X_RECORD, WORST_X_TAGS
        with db_session('core') as session:
            account = (
                session.query(Accounts)
                .filter(Accounts.id == account_id)
                .one_or_none()
            )
            if not account:
                return False, ""

            exam_r = (
                session.query(Exams)
                .filter(or_(Exams.id == account.exam_id, Exams.father_exam == account.exam_id))
                .all()
            )

            exam_ids = [x.id for x in exam_r]
            records = (
                session.query(Patterns)
                .filter(Patterns.exam_id.in_(exam_ids))
                .all()
            )

            _records = (
                session.query(
                    Patterns.pattern_name
                )
                .filter(Patterns.exam_id.in_(exam_ids))
                .group_by(Patterns.pattern_name)
                .all()
            )

            patterns = []
            for i in records:
                patterns.append(i.id)

            if len(patterns) > 0:
                current_date = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                date_days_ago = current_date - timedelta(days=offset)
                date_days_ago = date_days_ago.strftime("%Y-%m-%d")
                # 过去X天
                # raw_sql = text(f"""
                #     SELECT DISTINCTROW
                #         Patterns.pattern_name,
                #         ROUND(AVG(ASR.score), 2) as score
                #     FROM Patterns
                #     JOIN Sections S on Patterns.id = S.pattern_id
                #     JOIN Scores S3 on S.id = S3.section_id
                #     JOIN AnswerSheetRecord ASR on S3.answer_sheet_id = ASR.id
                #     WHERE Patterns.id IN {tuple(patterns)}
                #     AND ASR.account_id = {account_id}
                #     AND ASR.status = 0
                #     AND ASR.last_update_time >= {date_days_ago}
                #     AND ASR.score IS NOT NULL
                #     GROUP BY Patterns.pattern_name;
                # """)

                # 过去X次
                row_sql = text(f"""
                WITH RankedASR AS (
                    SELECT
                        ASR.id,
                        S.pattern_id,
                        ASR.score,
                        ROW_NUMBER() OVER(PARTITION BY S.pattern_id ORDER BY ASR.last_update_time DESC) AS rn
                    FROM AnswerSheetRecord ASR
                    JOIN Scores S3 on ASR.id = S3.answer_sheet_id
                    JOIN Sections S on S3.section_id = S.id
                    WHERE ASR.account_id = {account_id}
                    AND ASR.status = 0
                    AND ASR.score IS NOT NULL
                )
                SELECT
                P.pattern_name,
                ROUND(AVG(RASR.score), 2) as score
                FROM Patterns P
                JOIN Sections S on P.id = S.pattern_id
                JOIN Scores S3 on S.id = S3.section_id
                JOIN RankedASR RASR on S3.answer_sheet_id = RASR.id
                WHERE P.id IN {tuple(patterns)} AND RASR.rn <= {LAST_X_RECORD}
                GROUP BY P.pattern_name;
                """)
                scores = session.execute(row_sql).fetchall()

                raw_sql = text(f"""
                    WITH RankedASR AS (
                        SELECT
                            ASR.id,
                            S.pattern_id,
                            ASR.score,
                            ROW_NUMBER() OVER(PARTITION BY S.pattern_id ORDER BY ASR.last_update_time DESC) AS rn
                        FROM AnswerSheetRecord ASR
                        JOIN Scores S3 on ASR.id = S3.answer_sheet_id
                        JOIN Sections S on S3.section_id = S.id
                        WHERE ASR.account_id = {account_id}
                        AND ASR.status = 0
                        AND ASR.score IS NOT NULL
                    ), ScoreRecord AS (
                        SELECT
                            I.indicator_name AS name,
                            SUM(CASE WHEN S.score = S.max_score THEN 1 ELSE 0 END) AS sum,
                            COUNT(CASE WHEN S.score = S.max_score THEN 1 ELSE 0 END) AS count,
                            SUM(CASE WHEN S.score = S.max_score THEN 1 ELSE 0 END) / COUNT(CASE WHEN S.score = S.max_score THEN 1 ELSE 0 END) AS per,
                            ROW_NUMBER() OVER(PARTITION BY P.pattern_name ORDER BY SUM(CASE WHEN S.score = S.max_score THEN 1 ELSE 0 END) / COUNT(CASE WHEN S.score = S.max_score THEN 1 ELSE 0 END) ASC) AS rn,
                            P.pattern_name
                        FROM Indicators I
                        JOIN Indicators_Questions IQ on I.id = IQ.indicator_id
                        JOIN Questions Q on Q.id = IQ.question_id
                        JOIN Submissions S on Q.id = S.question_id
                        JOIN RankedASR RASR on RASR.id = S.answer_sheet_id
                        JOIN Sections S2 on Q.section_id = S2.id
                        JOIN Patterns P on S2.pattern_id = P.id
                        WHERE P.id IN {tuple(patterns)} AND RASR.rn <= {LAST_X_RECORD}
                        GROUP BY I.indicator_name, P.pattern_name
                    )
                    SELECT ScoreRecord.name, ScoreRecord.sum, ScoreRecord.count, ScoreRecord.per, pattern_name FROM ScoreRecord WHERE rn <= {WORST_X_TAGS};
                """)
                tag_details = session.execute(raw_sql).fetchall()

                res = {}
                for score in scores:
                    res[score.pattern_name] = {}
                    res[score.pattern_name]['avg_s'] = float(score.score)

                for rec in tag_details:
                    if rec.pattern_name in res:
                        if 'tag' not in res[rec.pattern_name]:
                            res[rec.pattern_name]['tag'] = []
                            res[rec.pattern_name]['tag'].append({
                                "name": rec.name,
                                "count": int(rec.count),
                                "per": float(rec.per),
                                "sum": int(rec.sum)
                            })
                        else:
                            res[rec.pattern_name]['tag'].append({
                                "name": rec.name,
                                "count": int(rec.count),
                                "per": float(rec.per),
                                "sum": int(rec.sum)
                            })
                    else:
                        pass

                for record in _records:
                    if record.pattern_name not in res:
                        res[record.pattern_name] = None

                return True, res
            else:
                return False, ""

    def _get_all_exams(self, active=None):
        with db_session('core') as session:
            if active:
                exams = (
                    session.query(Exams)
                    .filter(Exams.is_active == active)
                    .all()
                )
                return s.serialize_list(exams, self.default_not_show)
            else:
                exams = (
                    session.query(Exams)
                    .all()
                )
                return s.serialize_list(exams, self.default_not_show)

    def _get_all_patterns_under_exam(self, exam_id, active=None):
        with db_session('core') as session:
            exam = self._retrieve(model=Exams, restrict_field='id', restrict_value=exam_id)
            if exam:
                if active:
                    patterns = (
                        session.query(Patterns)
                        .filter(Patterns.exam_id == exam_id)
                        .filter(Patterns.is_active == active)
                        .all()
                    )
                    return s.serialize_list(patterns, self.default_not_show)
                else:
                    patterns = (
                        session.query(Patterns)
                        .filter(Patterns.exam_id == exam_id)
                        .all()
                    )
                    return s.serialize_list(patterns, self.default_not_show)
            else:
                return 'Invalid Exam Id'

    def _get_all_sections_under_pattern(self, pattern_id, active=None):
        with db_session('core') as session:
            pattern = self._retrieve(model=Patterns, restrict_field='id', restrict_value=pattern_id)
            if pattern:
                if active:
                    sections = (
                        session.query(Sections)
                        .filter(Sections.pattern_id == pattern_id)
                        .filter(Sections.is_active == active)
                        .all()
                    )
                    return s.serialize_list(sections, self.default_not_show)
                else:
                    sections = (
                        session.query(Sections)
                        .filter(Sections.pattern_id == pattern_id)
                        .all()
                    )
                    return s.serialize_list(sections, self.default_not_show)

            else:
                return 'Invalid Pattern Id'
    def _get_all_resources_under_exams(self, exam_id, account_id, page=0, limit=20):
        with db_session('core') as session:
            # 首先查找所有相关的exams
            redis = RedisWrapper("core_cache")
            cache_resource = redis.get(f"Resource-{exam_id}")
            if cache_resource:
                pass

            exam_record = (
                session.query(Exams)
                .filter(or_(Exams.id == exam_id, Exams.father_exam == exam_id))
                .all()
            )
            ids = tuple([record.id for record in exam_record])

            raw_sql = text(f"""
            WITH RECURSIVE tree AS (
                SELECT
                    id,
                    father_resource,
                    resource_name,
                    1 AS depth
                FROM Resources
                WHERE father_resource = -1
                AND exam_id IN {ids}
                UNION ALL
                SELECT
                    c.id,
                    c.father_resource,
                    c.resource_name,
                    p.depth + 1 AS depth
                FROM
                    Resources c
                JOIN tree p ON c.father_resource = p.id
                )
                SELECT T.*, Q.id As Q_id FROM tree T
                JOIN Questions Q on T.id = Q.source
                WHERE Q.father_question = -1
                ORDER BY father_resource, Q.`order`;
                """)

            questions_relations = session.execute(raw_sql).fetchall()
            q_r = {}
            for record in questions_relations:
                if record.father_resource not in q_r:
                    q_r[record.father_resource] = [record.Q_id]
                else:
                    q_r[record.father_resource].append(record.Q_id)

            raw_sql = text(f"""
            WITH RECURSIVE tree AS (
                SELECT
                    id,
                    father_resource,
                    resource_name,
                    1 AS depth
                FROM Resources
                WHERE father_resource = -1
                AND exam_id IN {ids}
                UNION ALL
                SELECT
                    c.id,
                    c.father_resource,
                    c.resource_name,
                    p.depth + 1 AS depth
                FROM
                    Resources c
                JOIN tree p ON c.father_resource = p.id
                )
                SELECT * FROM tree T
            """)

            resources = session.execute(raw_sql).fetchall()

            # 获取历史成绩记录
            raw_sql = text(f"""
                       WITH RankedSubmissions AS (
                          SELECT
                            ASR.id as sheet_id,
                            ASR.status,
                            ASR.father_sheet,
                            ASR.score,
                            ASR.max_score,
                            ROW_NUMBER() OVER(PARTITION BY ASR.id ORDER BY ASR.create_time DESC) AS rn,
                            R.father_resource
                          FROM AnswerSheetRecord ASR
                          JOIN Submissions S on ASR.id = S.answer_sheet_id
                          JOIN Questions Q on S.question_id = Q.id
                          JOIN Resources R on Q.source = R.id
                          JOIN Patterns P on R.pattern_id = P.id
                          LEFT JOIN Resources R2 on R.father_resource = R2.id
                          WHERE ASR.account_id = {account_id}
                            AND ASR.father_sheet != -1
                            AND ASR.status = 0
                        )
                        SELECT *
                        FROM RankedSubmissions
                        WHERE rn = 1;
                        """)

            grades = session.execute(raw_sql).fetchall()

            # 键值，加快检索速度
            grade_value = {}
            for grade in grades:
                if grade.father_resource not in grade_value:
                    grade_value[grade.father_resource] = grade

            tree = Tree()

            for record in resources:
                father_id = record.father_resource
                if record.father_resource == -1:
                    c_r = {
                        "id": record.id,
                        # "father_id": -1,
                        "resource_name": record.resource_name
                    }
                    tree.add_root(c_r)
                else:
                    if record.depth <= 3:
                        c_r = {
                            "id": record.id,
                            # "father_id": record.father_recource,
                            "resource_name": record.resource_name
                        }
                        if record.id in q_r:
                            c_r['questions'] = q_r[record.id]
                        if record.id in grade_value:
                            grade = grade_value[record.id]
                            c_r['sheet_id'] = grade.sheet_id
                            c_r['statue'] = grade.status
                            c_r['father_sheet'] = grade.father_sheet
                            c_r['score'] = grade.score
                            c_r['max_score'] = grade.max_score
                        else:
                            c_r['sheet_id'] = None
                            c_r['statue'] = None
                            c_r['father_sheet'] = None
                            c_r['score'] = None
                            c_r['max_score'] = None

                        tree.add_node("id", father_id, c_r)

            display_resource = [x for x in tree.print_tree() if x['resource_name'] == "TPO题库"]
            return True, display_resource

    def _get_all_resources_under_patterns(self, pattern_id, account_id, page=0, limit=20):
        with db_session('core') as session:
            start = time.time()
            # 首先查找所有相关的pattern => exams, => pattern
            exam_record = (
                session.query(Patterns)
                .filter(Patterns.id == pattern_id)
                .one_or_none()
            )
            if exam_record:
                exam_id = exam_record.exam_id
                pattern_name = exam_record.pattern_name
                exam_record = (
                    session.query(Exams)
                    .filter(or_(Exams.id == exam_id, Exams.father_exam == exam_id))
                    .all()
                )
                ids = [record.id for record in exam_record]

                patterns = (
                    session.query(Patterns)
                    .filter(and_(Patterns.exam_id.in_(ids), Patterns.pattern_name == pattern_name))
                    .all()
                )
                pattern_ids = [record.id for record in patterns]

                Parent = aliased(Resources, name='parent')
                Child = aliased(Resources, name='child')
                Question = aliased(Questions, name='Q')

                # Subquery J
                subquery_j = session.query(
                    Parent.id.label('parent_id'),
                    Parent.resource_name.label('parent_resource_name'),
                    Child.id.label('child_id'),
                    Child.resource_name.label('child_resource_name')
                ).select_from(
                    Parent
                ).outerjoin(
                    Child, Parent.id == Child.father_resource
                ).filter(
                    Parent.pattern_id.in_(pattern_ids),
                    Parent.section_id.is_(None),
                    Child.id.isnot(None)
                ).subquery('j')

                # Subquery for Questions linked to subquery J
                resources = session.query(
                    subquery_j.c.parent_id.label('resource_id'),
                    subquery_j.c.parent_resource_name.label('resource_name'),
                    subquery_j.c.child_id.label('section_id'),
                    subquery_j.c.child_resource_name.label('section_name'),
                    Question.id.label('question_id'),
                    Question.question_title.label('question_title'),
                    Question.order.label('order'),
                    Question.remark.label('remark')
                ).outerjoin(
                    Question, subquery_j.c.child_id == Question.source
                ).filter(
                    Question.father_question == -1
                ).all()

                # 获取历史做题数据 (性能会随数据增长而降低) => 后期可以考虑设一个时间范围或者单开表来存储最近的记录
                raw_sql = text(f"""
                            WITH SUB AS (
                                SELECT
                                father_question,
                                SUM(Submissions.score) AS child_score
                                FROM Submissions
                                JOIN Questions Q2 on Q2.id = Submissions.question_id
                                WHERE Q2.father_question != -1
                                GROUP BY Submissions.answer_sheet_id, Q2.father_question
                            ),
                            QuestionChildCount AS (
                              SELECT
                                father_question,
                                COUNT(*) AS child_count
                              FROM Questions
                              WHERE father_question != -1
                              GROUP BY father_question
                            ),
                            RankedSubmissions AS (
                              SELECT
                                S.question_id,
                                ASR.status,
                                S.score,
                                S.max_score,
                                ROW_NUMBER() OVER(PARTITION BY Q.id ORDER BY ASR.create_time DESC) AS rn,
                                COALESCE(QCC.child_count, 0) AS child_question_count,
                                SUB.child_score,
                                Q.remark,
                                ASR.id AS sheet_id
                              FROM Submissions S
                              JOIN AnswerSheetRecord ASR ON S.answer_sheet_id = ASR.id
                              JOIN Questions Q ON S.question_id = Q.id
                              LEFT JOIN QuestionChildCount QCC ON Q.id = QCC.father_question -- Added LEFT JOIN to include child question count
                              LEFT JOIN SUB ON S.question_id = SUB.father_question
                              JOIN Resources R ON Q.source = R.id
                              JOIN Patterns P ON R.pattern_id = P.id
                              WHERE P.id IN {tuple(pattern_ids)}
                                AND ASR.account_id = {account_id}
                                AND ASR.status = 0
                                AND Q.father_question = -1
                                AND (ASR.father_sheet = -1 OR ASR.father_sheet IS NULL)
                            )
                            SELECT *
                            FROM RankedSubmissions
                            WHERE rn = 1;
                            """)

                grades = session.execute(raw_sql).fetchall()
                grade_value = {}
                # 键值，加快检索速度
                for grade in grades:
                    if grade.question_id not in grade_value:
                        grade_value[grade.question_id] = grade

                # 数据解析
                resources_dic = {}
                for result in resources:
                    section = {}
                    if result.resource_id not in resources_dic:
                        resources_dic[result.resource_id] = {}
                        resources_dic[result.resource_id]['resource_id'] = result.resource_id
                        resources_dic[result.resource_id]['resource_name'] = result.resource_name
                        if result.section_id not in section:
                            section[result.section_id] = 1
                            resources_dic[result.resource_id]['section'] = []
                            question_dic = {
                                "question_id": result.question_id,
                                "question_name": result.question_title,
                                # "question_account": 10,
                                "order": result.order,
                                "remark": result.remark,
                            }
                            if result.question_id in grade_value:
                                grade = grade_value[result.question_id]
                                if grade_value[result.question_id].child_score is None:
                                    question_dic['last_record'] = grade.score
                                    question_dic['total'] = grade.max_score
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                                else:
                                    question_dic['last_record'] = grade.child_score
                                    question_dic['total'] = grade.child_question_count
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                            else:
                                question_dic['last_record'] = None
                                question_dic['total'] = None
                                question_dic['status'] = None
                                question_dic['sheet_id'] = None

                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [question_dic]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                        else:
                            question_dic = {
                                "question_id": result.question_id,
                                "question_name": result.question_title,
                                # "question_account": 10,
                                "order": result.order,
                                "remark": result.remark,
                            }
                            if result.question_id in grade_value:
                                grade = grade_value[result.question_id]
                                if grade_value[result.question_id].child_score is None:
                                    question_dic['last_record'] = grade.score
                                    question_dic['total'] = grade.max_score
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                                else:
                                    question_dic['last_record'] = grade.child_score
                                    question_dic['total'] = grade.child_question_count
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                            else:
                                question_dic['last_record'] = None
                                question_dic['total'] = None
                                question_dic['status'] = None
                                question_dic['sheet_id'] = None

                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [question_dic]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                    else:
                        if result.section_id not in section:
                            section[result.section_id] = 1
                            question_dic = {
                                "question_id": result.question_id,
                                "question_name": result.question_title,
                                # "question_account": 10,
                                "order": result.order,
                                "remark": result.remark,
                            }
                            if result.question_id in grade_value:
                                grade = grade_value[result.question_id]
                                if grade_value[result.question_id].child_score is None:
                                    question_dic['last_record'] = grade.score
                                    question_dic['total'] = grade.max_score
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                                else:
                                    question_dic['last_record'] = grade.child_score
                                    question_dic['total'] = grade.child_question_count
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                            else:
                                question_dic['last_record'] = None
                                question_dic['total'] = None
                                question_dic['status'] = None
                                question_dic['sheet_id'] = None

                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [question_dic]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                        else:
                            question_dic = {
                                "question_id": result.question_id,
                                "question_name": result.question_title,
                                # "question_account": 10,
                                "order": result.order,
                                "remark": result.remark,
                            }
                            if result.question_id in grade_value:
                                grade = grade_value[result.question_id]
                                if grade_value[result.question_id].child_score is None:
                                    question_dic['last_record'] = grade.score
                                    question_dic['total'] = grade.max_score
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                                else:
                                    question_dic['last_record'] = grade.child_score
                                    question_dic['total'] = grade.child_question_count
                                    question_dic['status'] = grade.status
                                    question_dic['sheet_id'] = grade.sheet_id
                            else:
                                question_dic['last_record'] = None
                                question_dic['total'] = None
                                question_dic['status'] = None
                                question_dic['sheet_id'] = None
                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [question_dic]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                return True, list(resources_dic.values())
            else:
                return False, "未查找到相关考试资源信息"


if __name__ == '__main__':
    init = TransactionsController()
    # pprint.pprint(init._get_all_resources_under_exams(1, 27))
    # pprint.pprint(init.get_recent_pattern_scores(20, 7))
    pprint.pprint(init._get_all_resources_under_patterns(pattern_id=11, account_id=20))

    # pprint.pprint(init.create_answer_sheet(account_id=7))
    # print(init.get_test_answers(sheet_id=7))
    # pprint.pprint(init.save_answer(sheet_id=7))
    # init.get_test_answers_history(account_id=7)

    init = AnsweringScoringController()
    # res = init.create_answer_sheet(account_id=37, question_ids=[223, 224])
    # res = init.create_mock_answer_sheet(account_id=27)
    # pprint.pprint(res)
    # sheet_id = res[1]['sheet_id']
    # pprint.pprint(init.get_test_answers(sheet_id=sheet_id))
    # pprint.pprint(init.get_mock_answer_sheet(sheet_id=906))

    # 暂停、继续试卷
    # print(init.pause_sheet(sheet_id=1148))
    # pprint.pprint(init.get_test_answers(sheet_id=1148, contin=True))

    # 做题
    # print(init.update_question_answer(sheet_id=1148, question_id=1220, answer_voice_link="https://obs-parrotcore.obs.cn-east-3.myhuaweicloud.com/Speaking_Grading_Sample.mp3"))
    # print(init.update_question_answer(sheet_id=sheet_id, question_id=5, answer=[0, 0, 1, 0], duration=200))

    # 中途批改
    # print(AnsweringScoringController().model_scoring(sheet_id=1224, question_id=1519))

    # 提交答案
    # pprint.pprint(init.save_answer(sheet_id=sheet_id))

    # 算分
    # start = time.time()
    # print(init.scoring(sheet_id=sheet_id))
    # print(init.get_score(answer_sheet_id=1757))
