import datetime
from blueprints.account.models import Accounts
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
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert, delete
import time
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import bindparam
from itertools import groupby
from operator import itemgetter
import random

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s
import json

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class QuestionController(crudController):
    """
    事务模块 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有事务表单(Projects, 问卷s, Sections, Resources)
    init: 先创建Projects => 问卷s => Sections, Resources
    """

    @staticmethod
    def select_records(group_, number):
        sorted_group = sorted(group_, key=lambda x: x['order'], reverse=True)
        top_two = sorted_group[:2]
        rest = sorted_group[2:]
        random_selection = random.sample(rest, min(len(rest), number - 2)) if len(rest) > number - 2 else rest
        return top_two + random_selection

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
                    "max_score": result.max_score,
                    "father_id": result.father_question,
                    "question_depth": result.d_level,
                    "keywords": json.loads(result.keywords),
                    "order": result.order
                }

                if result.father_question == -1:
                    root_questions.append(record)
                else:
                    refine_questions.append(record)

                redis_store[result.id] = record

            else:
                if result.question_stem:
                    merged_detail = {**json.loads(result.detail), **json.loads(result.q_detail),
                                     'd': result.question_stem.split(";")}
                else:
                    merged_detail = {**json.loads(result.detail), **json.loads(result.q_detail),
                                     'd': []}
                if not result.q_restriction:
                    merged_restrict = json.loads(result.restriction)
                else:
                    merged_restrict = {**json.loads(result.restriction), **json.loads(result.q_restriction)}

                if result.keywords:
                    k = json.loads(result.keywords)
                else:
                    k = None

                account_ans, duration = None, None
                if ac_type == 'create':
                    if result.stem_weights:
                        account_ans = [0] * len([int(num) for num in result.stem_weights.split(";")])
                        duration = None
                    else:
                        account_ans = ''
                        duration = None
                elif ac_type == 'get':
                    if fetch_question[result.id]['a']:
                        account_ans = [int(num) for num in fetch_question[result.id]['a'].split(";")]
                        duration = fetch_question[result.id]['d']
                    else:
                        account_ans = fetch_question[result.id]['a']
                        duration = fetch_question[result.id]['d']

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
                    "detail": merged_detail['d'] if 'd' in merged_detail else None,
                    "options_label": merged_detail['ol'] if 'ol' in merged_detail else None,
                    "answer_weight": [int(num) for num in
                                      result.stem_weights.split(";")] if result.stem_weights else None,
                    "answer": account_ans,
                    "duration": duration,
                    "restriction": merged_restrict
                }

                if ac_type == 'get':
                    record['score'] = fetch_question[result.id]['s']

                if result.father_question == -1:
                    root_questions.append(record)
                else:
                    refine_questions.append(record)

                redis_store[result.id] = record

        # --------- 跟section的题目进行比对，检查是否有过多题目，如果多于section的题目数，随机抽取 ---- #
        for key in sections.keys():
            r = (
                session.query(Sections)
                .filter(Sections.id == key)
                .one_or_none()
            )
            if r:
                sections[key] = r.no_questions

        # refine_questions.sort(key=lambda x: x['section_id'])
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
                    selected_records.extend(QuestionController.select_records(group_l, sections[section_id]))
            else:
                selected_records.extend(group_l)

        del refine_questions  # free the space

        # # --------   make a tree structure for front end -------- #
        tree = Tree()
        for question in root_questions:
            tree.add_root(question)
        for question in selected_records:
            tree.add_node("question_id", question["father_id"], question)

        res_questions = tree.print_tree()
        return res_questions, redis_store, list(sections.keys())


class AnsweringScoringController(crudController):
    def create_answer_sheet(self, account_id=None, type='practice', question_ids=None):
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
                                'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                                'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                            }
                            s_l.append(new_record)

                        session.execute(
                            insert(Scores),
                            s_l
                        )

                        default_dic = {'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)}

                        update_time = {
                            "id": sheet_id,
                            "start_time": datetime.datetime.now(tz=datetime.timezone.utc),
                            "end_time": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
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

    def get_test_answers(self, sheet_id, contin=False):
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
                        "time_remain": (record.end_time - datetime.datetime.utcnow()).total_seconds(),
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
                        print(time.time() - start)
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

                        res_questions, redis_store, sections = QuestionController().fetch_questions(
                            question_ids=question_ids,
                            session=session,
                            ac_type="get",
                            fetch_question=question_dic)

                        redis_dic = {
                            "sheet_id": sheet_id,
                            "is_time": record.is_time,
                            "is_check_answer": record.is_check_answer,
                            "time_remain": (
                                    record.end_time - record.last_pause_time).total_seconds() if record.status == 2 else 0,
                            "max_score": record.max_score,
                            "score": record.score if record.score else None,
                            "type": record.type.value,
                            "questions": redis_store
                        }
                        response['questions'] = res_questions
                        redis_cli = RedisWrapper('core_cache')
                        redis_cli.set(f'Sheet-non-{sheet_id}', redis_dic, ex=600)

                        if contin:
                            try:
                                update_s = {
                                    "id": sheet_id,
                                    "status": 1
                                }
                                self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                                session.commit()
                            except Exception as e:
                                session.rollback()
                                return False, str(e)
                        return True, response
            else:
                return False, "未找到答卷"

    def update_question_answer(self, sheet_id, question_id, duration, answer=None, answer_voice_link=None,
                               answer_video_link=None, upload_file_link=None):
        redis_cli = RedisWrapper('core_cache')
        cache_dict = redis_cli.get(f'Sheet-{sheet_id}')
        if cache_dict:
            if answer:
                cache_dict['questions'][str(question_id)][
                    'answer'] = answer  # Replace 'new_value' with the desired value
            if answer_voice_link:
                cache_dict['questions'][str(question_id)]['answer_voice_link'] = answer_voice_link
            if answer_video_link:
                cache_dict['questions'][str(question_id)]['answer_video_link'] = answer_video_link
            if upload_file_link:
                cache_dict['questions'][str(question_id)]['upload_file_link'] = upload_file_link
            cache_dict['questions'][str(question_id)]['duration'] = duration
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
                    if value['answer'] != [0] * 4:
                        value['is_answer'] = True
                    else:
                        value['is_answer'] = False
                    questions_li.append(value)
            return True, questions_li
        else:
            return False, "未找到答卷题目缓存"

    def pause_sheet(self, sheet_id):
        with db_session('core') as session:
            try:
                update_s = {
                    "id": sheet_id,
                    "status": 2
                }
                self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                session.commit()
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
                    if 'answer' in value and value['answer']:
                        if value['answer'][0] == '[' and value['answer'][-1] == ']':
                            single_answer = ';'.join(map(str, value['answer']))
                        else:
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
                        'upload_file_link': value['upload_file_link'] if 'upload_file_link' in value else None,
                        'answer_sheet_id': sheet_id,
                        'max_score': value['max_score'],
                        'is_graded': False,
                        'submit_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
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

    def get_score(self, answer_sheet_id):
        with db_session('core') as session:
            answer_record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.id == answer_sheet_id)
                .one_or_none()
            )
            if answer_record:
                if answer_record.status == 0:
                    l = s.serialize_dic(answer_record, self.default_not_show)
                    l['type'] = l['type'].value
                    resp, questions = self.get_test_answers(sheet_id=answer_sheet_id)
                    if resp:
                        l["questions_r"] = questions
                        return True, l
                    else:
                        return False, "未找到打分试卷"
                elif answer_record.status == 5 and answer_record.is_graded == 1:  # 完成批改但未登分
                    records = (
                        session.query(Scores)
                        .filter(Scores.answer_sheet_id == answer_sheet_id)
                        .all()
                    )
                    t_score = 0
                    for record in records:
                        t_score += record.score

                    update_s = {
                        "id": answer_sheet_id,
                        "score": t_score,
                        "status": 0,
                    }
                    self._update(model=AnswerSheetRecord, update_parameters=update_s, restrict_field="id")
                    re_s = s.serialize_dic(answer_record, self.default_not_show)
                    re_s['score'] = t_score
                    re_s['type'] = re_s['type'].value
                    re_s["status"] = 0
                    resp, questions = self.get_test_answers(sheet_id=answer_sheet_id)
                    if resp:
                        re_s["questions_r"] = questions
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

    def scoring(self, sheet_id):
        with db_session('core') as session:
            record = (
                session.query(AnswerSheetRecord)
                .filter(AnswerSheetRecord.id == sheet_id)
                .one_or_none()
            )
            if record:
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
                S.cal_method.label('cal_m'),
                S.max_score,
                Q.stem_weights.label('question_stem'),
                Q.question_type,
                Q.correct_answer,
                Q.section_id,
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
                if result.father_question != -1:
                    # merged_detail = {**json.loads(result.detail), **json.loads(result.q_detail), 'd': result.question_stem.split(";")}
                    if result.q_restriction:
                        merged_restrict = {**json.loads(result.restriction), **json.loads(result.q_restriction)}
                    else:
                        merged_restrict = json.loads(result.restriction)
                    question = {
                        'submission_id': result.submission_id,
                        'question_id': result.question_id,
                        'section_id': result.section_id,
                        'answer': [int(num) for num in result.answer.split(";")] if result.answer else None,
                        'correct': [int(num) for num in
                                    result.correct_answer.split(";")] if result.correct_answer else None,
                        'weight': [int(num) for num in
                                   result.question_stem.split(";")] if result.question_stem else None,
                        'max_score': result.max_score,
                        'father_id': result.father_question,
                        'rubric': json.loads(result.q_rubric),
                        # 'detail': merged_detail,
                        'restriction': merged_restrict,
                        'cal_method': result.cal_m,
                        'cal_fun': result.cal_m_B
                    }
                    score = getattr(grading_instance, question['cal_fun'])(
                        answer=question['answer'],
                        correct=question['correct'],
                        weight=question['weight'],
                        rubric=question['rubric'],
                        restriction=question['restriction'],
                        max_score=question['max_score']
                    )
                    question['score'] = score
                    questions.append(question)
                # else:
                #     question = {
                #         'submission_id': result.submission_id,
                #         'father_id': result.father_question,
                #         'question_id': result.question_id,
                #         'max_score': result.max_score,
                #         'score':None,
                #         'section_id': result.section_id,
                #     }
                #     q = question.copy()
                #     q['q'] = question
                #     roots.append(q)

            # tree = Tree()
            # for question in roots:
            #     tree.add_root(question)
            #
            # for question in questions:
            #     tree.add_node("question_id", question["father_id"], question)
            #
            # # 计算分数每个的root的分数
            # for root in tree.roots:
            #     root_score = tree.sum_children_scores(root)
            #     root_q = root.q.copy()
            #     root_q['score'] = root_score
            #     questions.append(root_q)

            from collections import defaultdict
            result = defaultdict(float)
            for d in questions:
                result[d["section_id"]] += d["score"]
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
                        s_r = {int(k): v for k, v in json.loads(rubric.rubric).items()}
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
                            "last_update_time": datetime.datetime.now(tz=datetime.timezone.utc)
                        }
                        u_r.append(new_record)
                else:
                    new_record = {
                        "answer_sheet_id": sheet_id,
                        "section_id": d['section_id'] if d['section_id'] else None,
                        "total_score": d['total_score'],
                        "score": s_r[d['total_score']] if s_r else None,
                        "max_score": max_score if max_score else None,
                        "last_update_time": datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    new_ = Scores(**new_record)
                    session.add(new_)

            # 更新成绩
            commit = []
            for question in questions:
                update_ = {
                    "s_id": question['submission_id'],
                    "is_graded": 1,
                    "score": question['score'],
                    "last_update_time": datetime.datetime.now(tz=datetime.timezone.utc)
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


class TransactionsController(crudController):
    """
    事务模块 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有事务表单(Projects, 问卷s, Sections, Resources)
    init: 先创建Projects => 问卷s => Sections, Resources
    """

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
                Submission = aliased(Submissions, name='S')
                Answer = aliased(AnswerSheetRecord, name='R')

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
                subquery_q = session.query(
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
                ).subquery('T')

                # Subquery for AnswerSheetRecord and Submission
                subquery_a = session.query(
                    Submission.id.label('submission_id'),
                    Submission.question_id.label('question_id'),
                    Answer.account_id.label('account_id'),
                    Answer.status.label('status'),
                    Submission.score.label('last_record')
                ).select_from(
                    Submission
                ).join(
                    Answer, Submission.answer_sheet_id == Answer.id
                ).filter(
                    Answer.account_id == account_id,
                ).order_by(
                    Submission.last_update_time.desc()
                ).limit(1).subquery('A')

                # Final outer query
                resources = session.query(
                    subquery_q,
                    subquery_a.c.submission_id,
                    subquery_a.c.account_id,
                    subquery_a.c.status,
                    subquery_a.c.last_record
                ).outerjoin(
                    subquery_a, subquery_q.c.question_id == subquery_a.c.question_id
                ).all()

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
                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [
                                    {
                                        "question_id": result.question_id,
                                        "question_name": result.question_title,
                                        "question_account": 10,
                                        "order": result.order,
                                        "remark": result.remark,
                                        "last_record": result.last_record,
                                        "status": result.status
                                    }
                                ]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                        else:
                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [
                                    {
                                        "question_id": result.question_id,
                                        "question_name": result.question_title,
                                        "question_account": 10,
                                        "order": result.order,
                                        "remark": result.remark,
                                        "last_record": result.last_record,
                                        "status": result.status
                                    }
                                ]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                        # response.append(resource_record)
                    else:
                        if result.section_id not in section:
                            section[result.section_id] = 1
                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [
                                    {
                                        "question_id": result.question_id,
                                        "question_name": result.question_title,
                                        "question_account": 10,
                                        "order": result.order,
                                        "remark": result.remark,
                                        "last_record": result.last_record,
                                        "status": result.status
                                    }
                                ]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)
                        else:
                            question_record = {
                                "section_id": result.section_id,
                                "section_name": result.section_name,
                                "questions": [
                                    {
                                        "question_id": result.question_id,
                                        "question_name": result.question_title,
                                        "question_account": 10,
                                        "order": result.order,
                                        "remark": result.remark,
                                        "last_record": result.last_record,
                                        "status": result.status
                                    }
                                ]
                            }
                            resources_dic[result.resource_id]['section'].append(question_record)

                # pprint.pprint(resources_dic)

                print(time.time() - start)
                return True, list(resources_dic.values())
            else:
                return False, "未查找到相关考试信息"


class InitController(crudController):
    """
    问题 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有问题相关表单(Questions, QuestionsType, Indicators, IndicatorQuestion)
    init: 先定义Indicators, QuestionsType => Questions => IndicatorQuestion
    """

    def build_listening_resources(self):
        indexes = list(range(2, 76))
        s_l = []
        with db_session('core') as session:
            for i in indexes:
                number = str(i)
                print(number)
                record = (
                    session.query(Resources)
                    .filter(Resources.resource_name == f'TPO{number}-阅读')
                    .one_or_none()
                )
                if record:
                    father_record = record.father_resource
                    if i <= 54:
                        exam_id = 2
                        pattern_id = 16
                    else:
                        exam_id = 1
                        pattern_id = 12

                    new = dict(
                        resource_name=f'TPO{number}-写作',
                        resource_eng_name=f'TPO{number}-Writing',
                        father_resource=father_record,
                        pattern_id=14,
                        exam_id=1,
                        is_active=1,
                        create_time=datetime.datetime.now(tz=datetime.timezone.utc),
                        last_update_time=datetime.datetime.now(tz=datetime.timezone.utc)
                    )
                    s_l.append(new)

            session.execute(
                insert(Resources),
                s_l
            )

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def build_resources(self):
        indexes = list(range(1, 76))
        with db_session('core') as session:
            for i in indexes:
                number = str(i)
                print(number)
                record = (
                    session.query(Resources)
                    .filter(Resources.resource_name == f'TPO{number}-写作')
                    .one_or_none()
                )
                if record:
                    father_record = record.id

                    if i < 64:
                        # exam_id = 1
                        # pattern_id = 14
                        # for index, j in enumerate(list(range(11, 13))):
                        #     new_resource = {
                        #         "resource_name": f'TPO{number}-写作-s{index + 1}',
                        #         "resource_eng_name": f'TPO{number}-Writing-s{index + 1}',
                        #         "father_resource": father_record,
                        #         "section_id": j,
                        #         "pattern_id": pattern_id,
                        #         "exam_id": exam_id,
                        #         "is_active": 1,
                        #         'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        #         'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                        #     }
                        #     n_record = Resources(**new_resource)
                        #     session.add(n_record)
                        pass

                    else:
                        exam_id = 1
                        pattern_id = 14
                        for index, j in enumerate(list(range(11, 13))):
                            new_resource = {
                                "resource_name": f'TPO{number}-写作-s{index + 1}',
                                "resource_eng_name": f'TPO{number}-Writing-s{index + 1}',
                                "father_resource": father_record,
                                "section_id": j,
                                "pattern_id": pattern_id,
                                "exam_id": exam_id,
                                "is_active": 1,
                                'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                                'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                            }
                            n_record = Resources(**new_resource)
                            session.add(n_record)

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def build_passages(self):
        file_path = '/Users/zhilinhe/Desktop/TPO1-34.txt/passage_1-34.json'
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            with db_session('core') as session:
                for each in data:
                    print(each['remark'])
                    resource_name = each['source']
                    record = (
                        session.query(Resources)
                        .filter(Resources.resource_name == resource_name)
                        .one_or_none()
                    )
                    if record:
                        source_id = record.id
                        each['source'] = source_id
                        default_dic = {
                            'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                            'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                        }
                        merged_dict = {**each, **default_dic}
                        record = Questions(**merged_dict)
                        session.add(record)

                try:
                    session.commit()
                    return True, ""
                except Exception as e:
                    session.rollback()
                    return False, str(e)

    def import_relationship(self):
        file_path = "/Users/zhilinhe/Desktop/Temp/Toefl Reading 1-72/generate_data/核心词汇.csv"
        import pandas as pd
        df = pd.read_csv(file_path)
        with db_session('core') as session:
            l = []
            words = {}
            for index, row in df.iterrows():
                if row['word'].lower() not in words:
                    words[row['word'].lower()] = 1
                    record_w = (
                        session.query(VocabBase)
                        .filter(VocabBase.word == row['word'].lower())
                        .one_or_none()
                    )
                    if record_w:
                        l.append(record_w.id)
                    if index % 100 == 0:
                        print(index)
            # for value in session.query(VocabBase.id).distinct():
            #     l.append(value[0])

            s_d = []
            s_l = []
            count = 0
            for i in l:
                new_record = {
                    "word_id": i,
                    "category_id": 2,
                    'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                    'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                }
                s_l.append(new_record)

                record_d = (
                    session.query(VocabCategoryRelationships)
                    .filter(VocabCategoryRelationships.word_id == i)
                    .filter(VocabCategoryRelationships.category_id == 1)
                    .one_or_none()
                )
                if record_d:
                    s_d.append(record_d.id)

                if count % 100 == 0:
                    print(count)
                count += 1

            print(len(s_l), len(s_d))

            session.execute(
                insert(VocabCategoryRelationships),
                s_l
            )
            session.execute(
                delete(VocabCategoryRelationships).where(VocabCategoryRelationships.id.in_(s_d)),
            )
            print("commit")
            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def import_vocabs(self):
        file_path = "/Users/zhilinhe/Desktop/Temp/Toefl Reading 1-72/generate_data/核心词汇.csv"
        import pandas as pd
        df = pd.read_csv(file_path)
        with db_session('core') as session:
            s_l = []
            words = {}
            for index, row in df.iterrows():
                if row['word'].lower() not in words:
                    record = (
                        session.query(VocabBase)
                        .filter(VocabBase.word == row['word'].lower())
                        .one_or_none()
                    )
                    if not record:
                        new_record = {
                            # "id": int(row['id']),
                            "word": row['word'].lower(),
                            "word_c": row['word_c'],
                            'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                            'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                        }
                        s_l.append(new_record)
                    words[row['word'].lower()] = 1
                    if index % 100 == 0:
                        print(index)

            session.execute(
                insert(VocabBase),
                s_l
            )
            print("commit")
            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def build_similarities(self):
        import pandas as pd
        df = pd.read_csv('simi.csv')
        df = df.where(pd.notnull(df), None)
        with db_session('core') as session:
            s_l = []
            for index, row in df.iterrows():
                new_record = {
                    "word_id": int(row['word_id']),
                    "similarities": row['similarity'],
                    'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                    'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                }
                s_l.append(new_record)

            session.execute(
                insert(VocabCategorySimilarities),
                s_l
            )
            print("commit")
            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def helper(self, content):
        first_newline_idx = content.find("\n")
        if first_newline_idx != -1:
            second_newline_idx = content.find("\n", first_newline_idx + 1)
            if second_newline_idx != -1:
                # Replace from the second "\n" onwards
                return content[:second_newline_idx] + content[second_newline_idx:].replace("\n", " ")

    def build_listening_questions(self):
        file_path = '/Users/zhilinhe/desktop/听力材料.xlsx'
        import pandas as pd
        df = pd.read_excel(file_path)
        with db_session('core') as session:
            for index, row in df.iterrows():
                record = (
                    session.query(Resources)
                    .filter(Resources.resource_name == f'{row["question_source"]}-听力-s{int(row["section_id"])}')
                    .one_or_none()
                )
                if record:
                    print(f'{row["question_source"]}-听力-s{int(row["section_id"])}')
                    new_q = {
                        "question_type": 4,
                        'question_title': row['question_title'].replace("\n", " ") if not pd.isnull(
                            row['question_title']) else None,
                        "question_content": self.helper(row['question_content']) if not pd.isnull(
                            row['question_content']) else None,
                        "question_stem": None,
                        "question_function_type": "exams",
                        "order": int(row["order"]),
                        "father_question": -1,
                        "cal_method": 0,
                        "max_score": 4,
                        "stem_weights": None,
                        'correct_answer': None,
                        "d_level": 0,
                        "is_require": 1,
                        "is_cal": 1,
                        "is_active": 1,
                        "voice_link": row['音频url'] if not pd.isnull(row['音频url']) else None,
                        "voice_content": row['文本内容'] if not pd.isnull(row['文本内容']) else None,
                        "is_attachable": 1,
                        "keywords": json.dumps({'p': 15, 'r': 45}) if int(row["order"]) == 1 else json.dumps(
                            {'p': 30, 'r': 60}),
                        "remark": f'{row["question_source"]} speaking question {int(row["order"])}',
                        "has_ans": 1,
                        "section_id": record.section_id,
                        "source": record.id,
                    }
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    merged_dict = {**new_q, **default_dic}
                    record = Questions(**merged_dict)
                    session.add(record)

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def build_writing_questions(self):
        file_path = '/Users/zhilinhe/desktop/写作题目.xlsx'
        import pandas as pd
        df = pd.read_excel(file_path)
        with db_session('core') as session:
            for index, row in df.iterrows():
                if row['Section Name'] == 'Integrated writing':
                    section_n = 1
                elif row['Section Name'] == 'Academic Disscussion':
                    section_n = 2

                record = (
                    session.query(Resources)
                    .filter(Resources.resource_name == f'{row["question_source"].replace(" ","")}-写作-s{section_n}')
                    .one_or_none()
                )
                if record:
                    print(f'{row["question_source"]}-写作-s{section_n}')
                    new_q = {
                        "question_type": 6,
                        'question_title': row['question_title'] if not pd.isnull(
                            row['question_title']) else None,
                        "question_content": row['question_content'] if not pd.isnull(
                            row['question_content']) else None,
                        "question_stem": None,
                        "question_function_type": "exams",
                        "order": 1,
                        "father_question": -1,
                        "cal_method": 0,
                        "max_score": 5,
                        "stem_weights": None,
                        'correct_answer': None,
                        "d_level": 0,
                        "is_require": 1,
                        "is_cal": 1,
                        "is_active": 1,
                        "voice_link": row['音频url'] if not pd.isnull(row['音频url']) else None,
                        "voice_content": row['音频文件'] if not pd.isnull(row['音频文件']) else None,
                        "is_attachable": 1,
                        "keywords": json.dumps({'r': 20*10}) if section_n == 1 else json.dumps(
                            {'r': 600}),
                        "remark": f'{row["question_source"]} writing section {section_n}',
                        "has_ans": 1,
                        "section_id": record.section_id,
                        "source": record.id,
                    }
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    merged_dict = {**new_q, **default_dic}
                    record = Questions(**merged_dict)
                    session.add(record)

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)


    def build_speaking_questions(self):
        file_path = '/Users/zhilinhe/desktop/口语题目材料.xlsx'
        import pandas as pd
        df = pd.read_excel(file_path)
        # print(df.isna().sum())
        with db_session('core') as session:
            for index, row in df.iterrows():
                record = (
                    session.query(Resources)
                    .filter(Resources.resource_name == f'{row["question_source"]}-口语-s1')
                    .one_or_none()
                )
                if record:
                    print(f'{row["question_source"]}-口语-s1-{int(row["order"])}')
                    new_q = {
                        "question_type": 4,
                        'question_title': row['question_title'].replace("\n", " ") if not pd.isnull(
                            row['question_title']) else None,
                        "question_content": self.helper(row['question_content']) if not pd.isnull(
                            row['question_content']) else None,
                        "question_stem": None,
                        "question_function_type": "exams",
                        "order": int(row["order"]),
                        "father_question": -1,
                        "cal_method": 0,
                        "max_score": 4,
                        "stem_weights": None,
                        'correct_answer': None,
                        "d_level": 0,
                        "is_require": 1,
                        "is_cal": 1,
                        "is_active": 1,
                        "voice_link": row['音频url'] if not pd.isnull(row['音频url']) else None,
                        "voice_content": row['文本内容'] if not pd.isnull(row['文本内容']) else None,
                        "is_attachable": 1,
                        "keywords": json.dumps({'p': 15, 'r': 45}) if int(row["order"]) == 1 else json.dumps(
                            {'p': 30, 'r': 60}),
                        "remark": f'{row["question_source"]} speaking question {int(row["order"])}',
                        "has_ans": 1,
                        "section_id": record.section_id,
                        "source": record.id,
                    }
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    merged_dict = {**new_q, **default_dic}
                    record = Questions(**merged_dict)
                    session.add(record)

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def build_questions(self):
        file_path = '/Users/zhilinhe/Desktop/TPO1-34.txt/q_1-12.xlsx'
        import pandas as pd
        df = pd.read_excel(file_path)
        with db_session('core') as session:
            for index, row in df.iterrows():
                record = (
                    session.query(Questions)
                    .filter(Questions.question_title == row["passage name"])
                    .one_or_none()
                )
                if record:
                    print(row['remark'])
                    new_q = {
                        "question_type": int(row["question_type"]),
                        "question_content": str(row["question content"]),
                        "question_stem": str(row["question stem"]) if not type(row["question stem"]) == float else None,
                        "question_function_type": "exams",
                        "order": int(row["order"]),
                        "father_question": record.id,
                        "cal_method": 1,
                        "max_score": int(row["question_type"]),
                        "stem_weights": str(row['correct_answer']),
                        'correct_answer': str(row['correct_answer']),
                        "d_level": 1,
                        "is_require": 1,
                        "is_cal": 1,
                        "is_active": 1,
                        "is_attachable": 0,
                        "keywords": str(row["keywords"]) if not type(row["question stem"]) == float else None,
                        "remark": str(row["remark"]),
                        "has_ans": 1,
                        "section_id": record.section_id,
                        "source": record.source,

                    }
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    merged_dict = {**new_q, **default_dic}
                    record = Questions(**merged_dict)
                    session.add(record)

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)


if __name__ == '__main__':
    #
    init = TransactionsController()
    pprint.pprint(init._get_all_resources_under_patterns(pattern_id=13, account_id=7))
    # init = InitController()
    # print(init.helper(None))
    # print(init.build_resources())
    # print(init.import_vocabs())
    # print(init.build_similarities())
    # print(init.build_questions())
    # pprint.pprint(init.create_answer_sheet(account_id=7))
    # print(init.get_test_answers(sheet_id=7))
    # pprint.pprint(init.save_answer(sheet_id=7))
    # init.get_test_answers_history(account_id=7)

    init = AnsweringScoringController()
    #res = init.create_answer_sheet(account_id=7, question_ids=[1220, 1221, 1222, 1223])
    # print(init.create_answer_sheet(account_id=7, question_ids=[1516, 1590]))
    # sheet_id = res[1]['sheet_id']
    # sheet_id = 59
    # print(init.get_test_answers(sheet_id=58))
    # pprint.pprint(init.get_test_answers(61)[1])
    # pprint.pprint(init.get_sheet_status(sheet_id=sheet_id))

    # 做题
    # print(init.update_question_answer(sheet_id=61, question_id=1590, answer='dashdksakhdh dashdkhasjkh dajskhdkhkajsh dashkjdkjh', duration=200))
    # print(init.update_question_answer(sheet_id=sheet_id, question_id=5, answer=[0, 0, 1, 0], duration=200))

    # 提交答案
    # print(init.save_answer(sheet_id=61))

    # 算分
    # start = time.time()
    # print(init.scoring(sheet_id=16))
    # pprint.pprint(init.get_score(answer_sheet_id=61))
    # print(time.time() - start)
