import pprint

from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session
from utils.redis_tools import RedisWrapper
import random
from utils import iso_ts
from datetime import datetime, timedelta, timezone
from configs.operation import WORDS_STUDY

def review_fetch_words_mc(
        account_id=None,
        **kwargs
):
    # 返回一个简单的词汇题目 #
    # 单词本保持 !!!右进左出!!!!!
    from blueprints.learning.models import VocabsLearning
    from blueprints.education.models import VocabBase, VocabCategorySimilarities
    redis_cache = RedisWrapper("core_cache")
    rds = RedisWrapper('core_learning')

    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if record:
            remain = len(rds.lrange(f"{record.to_review}"))
            today_list = rds.list_pop(f"{record.to_review}", side="l")

            if len(today_list) == 1:
                current_word_id = today_list[0]
                word_cache = redis_cache.get(f"Word:{current_word_id}")
                if word_cache:
                    return True, word_cache, True

                # 查找词汇的近义词
                record = (
                    session.query(VocabCategorySimilarities)
                    .filter(VocabCategorySimilarities.word_id == current_word_id)
                    .one_or_none()
                )
                if record:
                    words_return = None

                    # if record.similarities is not None:
                    #     words_return = [int(id) for id in record.similarities.split(";")[:3]]
                    #
                    # else:

                    # random generate
                    if True:
                        l = []
                        for value in session.query(VocabBase.id).distinct():
                            if value != current_word_id:
                                l.append(value[0])

                    words_return = random.sample(l, 3)

                position = random.randint(0, len(words_return))
                words_return.insert(position, current_word_id)
                rl = {}
                for i in range(len(words_return)):
                    rl[words_return[i]] = i

                w_records = (
                    session.query(VocabBase)
                    .filter(VocabBase.id.in_(words_return))
                    .all()
                )

                eng = ""
                stem = [None] * len(words_return)
                for word in w_records:
                    stem[rl[word.id]] = word.word_c
                    if word.id == current_word_id:
                        eng = word.word

                answer = [0] * len(words_return)
                answer[position] = 1
                response = dict(
                    word_id=current_word_id,
                    word=eng,
                    stem=stem,
                    word_ids=words_return,
                    correct_answer=answer,
                    answer=[0] * len(words_return),
                    unknown=False,
                    study=False,
                    target=["answer", "unknown", "study"]
                )
                redis_cache.set(f"Word:{current_word_id}", response, ex=86400)  # 缓存一天
                r = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == account_id)
                    .one_or_none()
                )
                if r:
                    response['today_review'] = r.today_day_review

                response['remain'] = remain
                return True, response, True

            elif len(today_list) == 0:
                return False, {}, True
            else:
                return False, "缓存出错", True
        else:
            return False, "无注册词汇学习表信息", True


def fetch_words_mc(
        account_id=None,
        **kwargs
):
    # 返回一个简单的词汇题目 #
    # 单词本保持 !!!右进左出!!!!!
    from blueprints.learning.models import VocabsLearning
    from blueprints.education.models import VocabBase, VocabCategorySimilarities, VocabCategoryRelationships
    redis_cache = RedisWrapper("core_cache")
    rds = RedisWrapper('core_learning')

    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if record:
            today_list = rds.list_pop(f"{record.today_learn}", side="l")

            if len(today_list) == 1:
                current_word_id = today_list[0]
                word_cache = redis_cache.get(f"Word:{current_word_id}")
                if word_cache:
                    return True, word_cache, True

                # 查找词汇的近义词
                record = (
                    session.query(VocabCategorySimilarities)
                    .filter(VocabCategorySimilarities.word_id == current_word_id)
                    .one_or_none()
                )
                if record:
                    words_return = None
                    # if record.similarities is not None:
                    #     words_return = [int(id) for id in record.similarities.split(";")[:3]]
                    #
                    # else:

                    # random generate
                    if True:
                        l = []
                        for value in session.query(VocabBase.id).distinct():
                            if value != current_word_id:
                                l.append(value[0])

                        words_return = random.sample(l, 3)

                position = random.randint(0, len(words_return))
                words_return.insert(position, current_word_id)
                rl = {}
                for i in range(len(words_return)):
                    rl[words_return[i]] = i

                w_records = (
                    session.query(VocabBase)
                    .filter(VocabBase.id.in_(words_return))
                    .all()
                )

                eng = ""
                stem = [None] * len(words_return)
                for word in w_records:
                    stem[rl[word.id]] = word.word_c
                    if word.id == current_word_id:
                        eng = word.word

                answer = [0] * len(words_return)
                answer[position] = 1
                response = dict(
                    word_id=current_word_id,
                    word=eng,
                    stem=stem,
                    word_ids=words_return,
                    correct_answer=answer,
                    answer=[0] * len(words_return),
                    unknown=False,
                    study=False,
                    target=["answer", "unknown", "study"]
                )
                redis_cache.set(f"Word:{current_word_id}", response, ex=86400)  # 缓存一天
                r = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == account_id)
                    .one_or_none()
                )
                if r:
                    response['today_study'] = r.today_day_study

                curr = len(rds.lrange(f"{account_id}:wrong_group")) if rds.lrange(f"{account_id}:wrong_group") else 0
                total = WORDS_STUDY
                response['process'] = {"c": curr, "t": total}
                return True, response, True

            elif len(today_list) == 0:
                # 整个都学习完了
                if len(rds.lrange(f"{record.in_proccess}")) == 0:
                    return False, "词汇已学习完毕", True
                else:
                    return False, "今日已达学习上限", True
            else:
                return False, "缓存出错", True
        else:
            return False, "无注册词汇学习表信息", True


def words_gpt_fetch(
        account_id=None,
        **kwargs
):
    rds = RedisWrapper('core_learning')
    list_words = rds.lrange(f"{account_id}:wrong_group")
    rds.set(f"{account_id}:loop_study", len(list_words))
    from blueprints.learning.models import VocabsLearning
    from blueprints.education.models import VocabBase
    with db_session('core') as session:
        records = (
            session.query(VocabBase)
            .filter(VocabBase.id.in_(list_words))
            .all()
        )
        ls = {}
        for record in records:
            ls[record.word] = record.word_c

        payload = dict(
            endpoints={
                "init":{
                    "url": f"http://18.136.105.171:57875/v1/modelapi/streaming/",
                    "method": "post",
                    "input": ls,
                    "output": "clientId",
                    "successCode":10000
                },
                "streaming":{
                    "url": "http://18.136.105.171:57875/v1/modelapi/getVocabContent/{ClientID}/",
                    "method": "sse",
                }
            },
            response='',
            execute=False,
            target=['execute', 'response']
        )
        r = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if r:
            payload['today_study'] = r.today_day_study

        curr = len(rds.lrange(f"{account_id}:wrong_group")) if rds.lrange(f"{account_id}:wrong_group") else 0
        total = WORDS_STUDY
        payload['process'] = {"c": curr, "t": total}
        return True, payload, True


def review_words(
        account_id=None,
        **kwargs
):
    # 找错题集的第一个，查找题目cache，返回，没有再做搜索
    from blueprints.learning.models import VocabsLearning
    from blueprints.education.models import VocabBase, VocabCategorySimilarities
    redis_cache = RedisWrapper("core_cache")
    model_response = redis_cache.get(f"Wording:{account_id}")

    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if record:
            rds = RedisWrapper('core_learning')
            today_list = rds.list_pop(f"{account_id}:wrong_group", side="l")
            remain = len(rds.lrange(f"{account_id}:wrong_group"))
            loop_study = rds.get(f"{account_id}:loop_study")

            if len(today_list) == 1:
                current_word_id = today_list[0]
                word_cache = redis_cache.get(f"Word:{current_word_id}")
                if word_cache:
                    word = word_cache['word']
                    if model_response:
                        hint = None
                        resp_l = model_response.split(")")
                        for each in resp_l:
                            if word in each:
                                hint = each
                                break
                        word_cache['hint'] = hint
                        return True, word_cache, True
                    else:
                        return True, word_cache, True

                # 查找词汇的近义词
                record = (
                    session.query(VocabCategorySimilarities)
                    .filter(VocabCategorySimilarities.word_id == current_word_id)
                    .one_or_none()
                )
                if record:
                    words_return = None
                    # if record.similarities is not None:
                    #     words_return = [int(id) for id in record.similarities.split(";")[:3]]
                    #
                    # else:
                    if True:
                        # random generate
                        l = []
                        for value in session.query(VocabBase.id).distinct():
                            if value != current_word_id:
                                l.append(value[0])

                        words_return = random.sample(l, 3)

                position = random.randint(0, len(words_return))
                words_return.insert(position, current_word_id)
                rl = {}
                for i in range(len(words_return)):
                    rl[words_return[i]] = i

                w_records = (
                    session.query(VocabBase)
                    .filter(VocabBase.id.in_(words_return))
                    .all()
                )

                eng = ""
                stem = [None] * len(words_return)
                for _word in w_records:
                    stem[rl[_word.id]] = _word.word_c
                    if _word.id == current_word_id:
                        eng = _word.word

                answer = [0] * len(words_return)
                answer[position] = 1
                response = dict(
                    word_id=current_word_id,
                    word=eng,
                    stem=stem,
                    word_ids=words_return,
                    correct_answer=answer,
                    answer=[0] * len(words_return),
                    unknown=False,
                    study=False,
                    target=["answer", "unknown", "study"]
                )
                redis_cache.set(f"Word:{current_word_id}", response, ex=86400)  # 缓存一天
                if model_response:
                    hint = None
                    resp_l = model_response.split(")")
                    for each in resp_l:
                        if eng in each:
                            hint = each
                            break
                    response['hint'] = hint

                response['process'] = {"c": loop_study - remain if loop_study else WORDS_STUDY - remain, "t": loop_study if loop_study else WORDS_STUDY}
                return True, response, True
            elif len(today_list) == 0:
                redis_cache.delete(f"{account_id}:loop_study")
                return False, "复习已完成", True
            else:
                return False, "缓存出错", True
        else:
            return False, "无注册词汇学习表信息", True


def out_loop(
        current_loop,
        loop,
        task_account_id,
        **kwargs
):
    from blueprints.learning.models import TaskAccounts
    with db_session('core') as session:
        next_current_loop = current_loop + 1
        record = (
            session.query(TaskAccounts)
            .filter(TaskAccounts.id == task_account_id)
            .update({
                TaskAccounts.last_update_time: iso_ts(),
                TaskAccounts.current_loop: next_current_loop,
                TaskAccounts.complete_percentage: next_current_loop / loop * 100
            })
        )
        try:
            session.commit()
            return True, "OK.", False
        except Exception as e:
            session.rollback()
            return False, str(e), False


# =================== out functions (only two response) ======================== #
def reviews_redo_words_study(
        payload,
        account_id,
        **kwargs
):
    # 缓存 statiscs
    # 数据库 statisc: vocablearning: today study, total study
    # 数据库 records 词表， study word, correct word, wrong word
    from blueprints.learning.models import VocabsLearning, VocabsLearningRecords
    word_id, correct_answer, answer, unknown, study = payload['word_id'], payload['correct_answer'], payload['answer'], \
                                                      payload['unknown'], payload['study']
    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if not record:
            return False, "未找到单词账户"

        try:
            rds = RedisWrapper('core_learning')
            redis = RedisWrapper('core_cache')
            statistic_cache = redis.get(f'VocabsStatics:{account_id}')
            now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            tody = now.strftime('%Y-%m-%d')

            if correct_answer != answer:
                # wrong word 1 条记录

                if statistic_cache:
                    if tody in statistic_cache['series']:
                        if type(statistic_cache['series'][tody]['wrong_words']) == list:
                            statistic_cache['series'][tody]['wrong_words'][0] += 1
                        elif type(statistic_cache['series'][tody]['wrong_words']) == int:
                            statistic_cache['series'][tody]['wrong_words'] += 1

                rds.list_push(f"{record.to_review}", *[word_id], side="r")

                total_len = len(rds.lrange(f"{record.to_review}"))

                wrong_add = dict(
                    wrong_word_id=word_id,
                    account_id=account_id,
                    time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )
                session.add(VocabsLearningRecords(**wrong_add))

                try:
                    session.commit()
                    redis.set(f'VocabsStatics:{account_id}', statistic_cache, 3600)

                    # 如果今天的已经复习了,下一步
                    if total_len > 0:
                        return True, False
                    else:
                        return True, True

                except Exception as e:
                    return False, "单词学习过程中入库失败."

            elif correct_answer == answer:
                # 加入finished group
                if statistic_cache:
                    statistic_cache['today_day_review'] += 1
                    statistic_cache['total_review'] += 1

                    if tody in statistic_cache['series']:
                        if type(statistic_cache['series'][tody]['correct_words']) == list:
                            statistic_cache['series'][tody]['correct_words'][0] += 1
                        elif type(statistic_cache['series'][tody]['correct_words']) == int:
                            statistic_cache['series'][tody]['correct_words'] += 1

                # correct word 1 条记录
                study_add = dict(
                    account_id=account_id,
                    correct_word_id=word_id,
                    time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )
                session.add(VocabsLearningRecords(**study_add))

                # 更新learning （大量写入，可能会导致瓶颈）
                update_p = dict(
                    today_day_review=record.today_day_review + 1,
                    total_review=record.total_review + 1,
                    last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )

                record_update = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == account_id)
                    .update({**update_p})
                )

                try:
                    session.commit()
                    redis.set(f'VocabsStatics:{account_id}', statistic_cache, 3600)
                    total_len = len(rds.lrange(f"{record.to_review}"))
                    if total_len > 0:
                        return True, False
                    else:
                        return True, True
                except Exception as e:
                    return False, "单词学习过程中入库失败."

        except Exception as e:
            return False, str(e)


def redo_words_study(
        payload,
        account_id,
        **kwargs
):
    # 缓存 statiscs
    # 数据库 statisc: vocablearning: today study, total study
    # 数据库 records 词表， study word, correct word, wrong word
    from blueprints.education.models import VocabCategoryRelationships
    from blueprints.learning.models import VocabsLearning, VocabsLearningRecords
    from blueprints.account.models import Users, Accounts
    word_id, correct_answer, answer, unknown, study = payload['word_id'], payload['correct_answer'], payload['answer'], \
                                                      payload['unknown'], payload['study']
    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if not record:
            return False, "未找到单词账户"

        try:
            cate = record.current_category
            rds = RedisWrapper('core_learning')
            redis = RedisWrapper('core_cache')
            statistic_cache = redis.get(f'VocabsStatics:{account_id}')
            now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            tody = now.strftime('%Y-%m-%d')

            if study:
                # 放回
                rds.list_push(f"{record.today_learn}", *[word_id], side="l")  # 这里是放回左边，第一个
                return True, True

            elif unknown:
                rds.list_push(f"{record.unknown}", *[word_id], side="r")
                rds.list_push(f"{record.to_review}", *[word_id], side="r")
                rds.list_push(f"{account_id}:wrong_group", *[word_id], side="r")

                total_len = len(rds.lrange(f"{account_id}:wrong_group"))

                if total_len < WORDS_STUDY:
                    return True, False
                else:
                    return True, True

            elif correct_answer != answer:
                # wrong word 1 条记录
                if statistic_cache:
                    if tody in statistic_cache['series']:
                        if type(statistic_cache['series'][tody]['wrong_words']) == list:
                            statistic_cache['series'][tody]['wrong_words'][0] += 1
                        elif type(statistic_cache['series'][tody]['wrong_words']) == int:
                            statistic_cache['series'][tody]['wrong_words'] += 1

                rds.list_push(f"{account_id}:wrong_group", *[word_id], side="r")
                rds.list_push(f"{record.to_review}", *[word_id], side="r")

                total_len = len(rds.lrange(f"{account_id}:wrong_group"))

                wrong_add = dict(
                    wrong_word_id=word_id,
                    account_id=account_id,
                    time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )
                session.add(VocabsLearningRecords(**wrong_add))

                study_left = len(rds.lrange(f"{record.today_learn}"))
                try:
                    session.commit()
                    redis.set(f'VocabsStatics:{account_id}', statistic_cache, 3600)

                    # 如果今天的已经学完了，直接请求model,下一步
                    if study_left == 0:
                        return True, True

                    if total_len < WORDS_STUDY:
                        return True, False
                    else:
                        return True, True

                except Exception as e:
                    return False, "单词学习过程中入库失败."

            elif correct_answer == answer:
                # 加入finished group

                if statistic_cache:
                    statistic_cache['today_day_study'] += 1
                    statistic_cache['total_study'] += 1
                    statistic_cache['vocab'] += 1
                    statistic_cache["status_book"]["level_status"] += 1

                    if tody in statistic_cache['series']:
                        if type(statistic_cache['series'][tody]['correct_words']) == list:
                            statistic_cache['series'][tody]['correct_words'][0] += 1
                        elif type(statistic_cache['series'][tody]['correct_words']) == int:
                            statistic_cache['series'][tody]['correct_words'] += 1

                word = (
                    session.query(VocabCategoryRelationships)
                    .filter(VocabCategoryRelationships.word_id == word_id)
                    .one_or_none()
                )
                if word:
                    if word.category_id > cate:
                        cate_record = (
                            session.query(VocabsLearning)
                            .filter(VocabsLearning.account_id == account_id)
                            .update({VocabsLearning.current_category: word.category_id})
                        )
                        if statistic_cache:
                            statistic_cache['status_book']["current_level"] = word.category_id
                            statistic_cache['status_book']["level_status"] = 1
                            for each in statistic_cache['status_book']['level_book']:
                                if each['id'] == word.category_id:
                                    statistic_cache['status_book']["level_total"] = each['counts']

                # study word, correct word 2 条记录
                study_add = dict(
                    account_id=account_id,
                    study_word_id=word_id,
                    correct_word_id=word_id,
                    time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )
                session.add(VocabsLearningRecords(**study_add))

                user_r = (
                    session.query(Users)
                    .join(Accounts, Accounts.user_id == Users.id)
                    .filter(Accounts.id == account_id)
                    .one_or_none()
                )

                if not user_r:
                    return False, "用户信息未找到"

                # 更新user vocab 词汇:
                user = (
                    session.query(Users)
                    .filter(Users.id == user_r.id)
                    .update({
                        Users.vocab_level: Users.vocab_level + 1 if Users.vocab_level is not None else 1,
                        Users.last_update_time: datetime.now(timezone.utc).astimezone(
                            timezone(timedelta(hours=8))),
                    })
                )

                # 更新learning （大量写入，可能会导致瓶颈）
                update_p = dict(
                    today_day_study=record.today_day_study + 1,
                    total_study=record.total_study + 1,
                    last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )

                record_update = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == account_id)
                    .update({**update_p})
                )

                rds.list_push(f"{account_id}:finished", *[word_id], side="r")
                try:
                    session.commit()
                    if statistic_cache:
                        redis.set(f'VocabsStatics:{account_id}', statistic_cache, 3600)
                    return True, False
                except Exception as e:
                    return False, "单词学习过程中入库失败."

        except Exception as e:
            return False, str(e)


def words_gpt_execute(
        payload,
        account_id,
        **kwargs
):
    try:
        if payload['execute']:
            rds = RedisWrapper('core_cache')
            model_response = payload['response']
            rds.set(f"Wording:{account_id}", model_response)
            return True, {}
        return False, ""
    except Exception as e:
        return False, str(e)


def redo_review_study(
        payload,
        account_id,
        **kwargs
):
    from blueprints.learning.models import VocabsLearning, VocabsLearningRecords
    from blueprints.education.models import VocabCategoryRelationships
    from blueprints.account.models import Users, Accounts
    word_id, correct_answer, answer = payload['word_id'], payload['correct_answer'], payload['answer']
    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
            .one_or_none()
        )
        if not record:
            return False, "未找到单词账户"

        try:
            rds = RedisWrapper('core_learning')
            redis = RedisWrapper('core_cache')
            statistic_cache = redis.get(f'VocabsStatics:{account_id}')
            now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            tody = now.strftime('%Y-%m-%d')
            cate = record.current_category

            # wrong_word = rds.list_pop(f"{account_id}:wrong_group", side='l')
            #
            # if len(wrong_word) == 1:
            #     current_word_id = wrong_word[0]
            if correct_answer != answer:
                # 还不对，继续添加到最后
                if statistic_cache:
                    if tody in statistic_cache['series']:
                        if type(statistic_cache['series'][tody]['wrong_words']) == list:
                            statistic_cache['series'][tody]['wrong_words'][0] += 1
                        elif type(statistic_cache['series'][tody]['wrong_words']) == int:
                            statistic_cache['series'][tody]['wrong_words'] += 1

                rds.list_push(f"{account_id}:wrong_group", *[word_id], side="r")
                rds.list_push(f"{record.to_review}", *[word_id], side="r")

                wrong_add = dict(
                    wrong_word_id=word_id,
                    account_id=account_id,
                    time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )
                session.add(VocabsLearningRecords(**wrong_add))

                study_left = len(rds.lrange(f"{record.total_study}"))
                try:
                    session.commit()
                    redis.set(f'VocabsStatics:{account_id}', statistic_cache, 3600)
                    return True, False

                except Exception as e:
                    return False, "单词学习过程中入库失败."

            else:
                # 加入finished group
                if statistic_cache:
                    statistic_cache['today_day_study'] += 1
                    statistic_cache['total_study'] += 1
                    statistic_cache['vocab'] += 1
                    # 操作防止在复习过程中完成了跳级, 导致数对不上
                    word = (
                        session.query(VocabCategoryRelationships)
                        .filter(VocabCategoryRelationships.word_id == word_id)
                        .one_or_none()
                    )
                    if word:
                        if word.category_id == cate:
                            statistic_cache['status_book']["level_status"] += 1

                    if tody in statistic_cache['series']:
                        if type(statistic_cache['series'][tody]['correct_words']) == list:
                            statistic_cache['series'][tody]['correct_words'][0] += 1
                        elif type(statistic_cache['series'][tody]['correct_words']) == int:
                            statistic_cache['series'][tody]['correct_words'] += 1

                # study word, correct word 2 条记录
                # user vocab 词汇:
                user_r = (
                    session.query(Users)
                    .join(Accounts, Accounts.user_id == Users.id)
                    .filter(Accounts.id == account_id)
                    .one_or_none()
                )

                if not user_r:
                    return False, "用户信息未找到"

                # 更新user vocab 词汇:
                user = (
                    session.query(Users)
                    .filter(Users.id == user_r.id)
                    .update({
                        Users.vocab_level: Users.vocab_level + 1 if Users.vocab_level is not None else 1,
                        Users.last_update_time: datetime.now(timezone.utc).astimezone(
                            timezone(timedelta(hours=8))),

                    })
                )
                study_add = dict(
                    account_id=account_id,
                    study_word_id=word_id,
                    correct_word_id=word_id,
                    time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )
                session.add(VocabsLearningRecords(**study_add))

                # 更新learning （大量写入，可能会导致瓶颈）
                update_p = dict(
                    today_day_study=record.today_day_study + 1,
                    total_study=record.total_study + 1,
                    last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                )

                record_update = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == account_id)
                    .update({**update_p})
                )

                rds.list_push(f"{account_id}:finished", *[word_id], side="r")
                try:
                    session.commit()
                    redis.set(f'VocabsStatics:{account_id}', statistic_cache, 3600)

                    study_left = len(rds.lrange(f"{account_id}:wrong_group"))
                    if study_left > 0:
                        return True, False
                    else:
                        return True, True
                except Exception as e:
                    session.rollback()
                    return False, "单词学习过程中入库失败."
        except Exception as e:
            return False, str(e)


def re_loop(
        task_account_id,
        **kwargs
):
    from blueprints.learning.models import VocabsLearning, TaskAccounts
    with db_session('core') as session:
        record = (
            session.query(TaskAccounts)
            .filter(TaskAccounts.id == task_account_id)
            .one_or_none()
        )
        if record:
            if record.loop > record.current_loop:
                return True, "redo"
            else:
                # 执行finished
                record = (
                    session.query(TaskAccounts)
                    .filter(TaskAccounts.id == task_account_id)
                    .update({
                        TaskAccounts.is_complete: 1,
                        TaskAccounts.status: 2,
                        TaskAccounts.finished_time: datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                        TaskAccounts.last_update_time: datetime.now(timezone.utc).astimezone(
                            timezone(timedelta(hours=8))),
                    })
                )
                redis = RedisWrapper('core_cache')
                redis.delete(f"TaskAccount:{task_account_id}")
                try:
                    session.commit()
                    return True, "finished"
                except:
                    session.rollback()
                    return False, "数据库出错."

        else:
            return False, "未找到record"


if __name__ == "__main__":
    print(fetch_words_mc(account_id=27))
