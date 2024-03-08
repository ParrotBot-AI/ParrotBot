from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session
from utils.redis_tools import RedisWrapper
import json
import random
from utils import iso_ts
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert, delete


def fetch_words_mc(
        account_id=4,
        **kwargs
):
    # 返回一个简单的词汇题目 #
    from blueprints.learning.models import VocabsLearning
    from blueprints.education.models import VocabBase, VocabCategorySimilarities
    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
        )
        if record:
            rds = RedisWrapper('core_learning')
            rds.set(f"{account_id}:today", "34001;34002;34003;34005;34005")
            today_list = rds.get(f"{account_id}:today")
            if today_list:
                today_list = today_list.split(";")
                current_word_id = int(today_list[0])

                # 查找词汇的近义词
                record = (
                    session.query(VocabCategorySimilarities)
                    .filter(VocabCategorySimilarities.word_id == current_word_id)
                    .one_or_none()
                )
                if record:
                    words_return = None
                    if record.similarities is not None:
                        words_return = [int(id) for id in record.similarities.split(";")[:3]]

                    else:
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
                    target=["answer"]
                )
                return True, response, True
            else:
                return False, "未找到词汇记录list，检查redis存储", True
        else:
            return False, "无注册词汇学习表信息", True


def wrong_words_mc(**kwargs):
    ## add the word to the review list
    ##
    return True, "wrong_words", True


def out_loop(
        task_id,
        current_loop,
        task_account_id,
        **kwargs
):
    from blueprints.learning.models import VocabsLearning, TaskAccounts
    with db_session('core') as session:
        next_current_loop = current_loop + 1
        record = (
            session.query(TaskAccounts)
            .filter(TaskAccounts.id == task_account_id)
            .update({
                TaskAccounts.last_update_time: iso_ts(),
                TaskAccounts.current_loop: next_current_loop,
            })
        )
        try:
            session.commit()
            # 加入词汇到finish，从today中删除， 加入到review词库
            return True, "OK.", False
        except Exception as e:
            session.rollback()
            return False, str(e), False


def words_gpt_fetch(**kwargs):
    payload = dict(
        endpoint='gpt-endpint',
        method='sse',
        api_key="key",
        execute=False,
        target=['execute']
    )
    return True, payload, True


def review_words(
        account_id=4,
        **kwargs
):
    # 找错题集的第一个，查找题目cache，返回，没有再做搜索
    from blueprints.learning.models import VocabsLearning
    from blueprints.education.models import VocabBase, VocabCategorySimilarities
    with db_session('core') as session:
        record = (
            session.query(VocabsLearning)
            .filter(VocabsLearning.account_id == account_id)
        )
        if record:
            rds = RedisWrapper('core_learning')
            rds.set(f"{account_id}:today", "34001;34002;34003;34005;34005")
            today_list = rds.get(f"{account_id}:today")
            if today_list:
                today_list = today_list.split(";")
                current_word_id = int(today_list[0])

                # 查找词汇的近义词
                record = (
                    session.query(VocabCategorySimilarities)
                    .filter(VocabCategorySimilarities.word_id == current_word_id)
                    .one_or_none()
                )
                if record:
                    words_return = None
                    if record.similarities is not None:
                        words_return = [int(id) for id in record.similarities.split(";")[:3]]

                    else:
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
                    target=["answer"]
                )
                return True, response, True
            else:
                return False, "未找到词汇记录list，检查redis存储", True
        else:
            return False, "无注册词汇学习表信息", True


# =================== out functions ======================== #
def redo_words_study(
        payload,
        account_id,
        **kwargs
):
    word_id, correct_answer, answer = payload['word_id'], payload['correct_answer'], payload['answer']
    try:
        if correct_answer != answer:
            rds = RedisWrapper('core_learning')

            # 添加到错题和review库
            print(account_id)
            wrong_group = rds.get(f"{account_id}:wrong_group")
            if wrong_group:
                wrong_group += f";{word_id}"
                rds.set(f"{account_id}:wrong_group", wrong_group)
                total_len = len(wrong_group.split(";"))

                # add to review list (to do)
                print(wrong_group.split(";"))
                print(total_len)
                if total_len < 2:
                    return True, False
                else:
                    rds.delete(f"{account_id}:wrong_group")
                    return True, True

            else:
                s = f'{word_id}'
                rds.set(f"{account_id}:wrong_group", s)
                return True, False
        else:
            # 加入finished group

            return True, False
    except Exception as e:
        return False, str(e)


def words_gpt_execute(
        payload,
        **kwargs
):
    try:
        if payload['execute']:
            return True, {}
        return False, ""
    except Exception as e:
        return False, str(e)


def redo_review_study(
        payload,
        account_id,
        **kwargs
):
    word_id, correct_answer, answer = payload['word_id'], payload['correct_answer'], payload['answer']
    try:
        # ru guo 还是不对的话，添加到最后
        rds = RedisWrapper('core_learning')
        # 添加到错题和review库
        print(account_id)
        rds.set("4:today", 'okokok')
        wrong_group = rds.get("4:today")
        print(wrong_group, 273)
        if correct_answer != answer:
            if wrong_group:
                wrong_group += f";{word_id}"
                rds.set(f"{account_id}:wrong_group", wrong_group)
                return True, False
            else:
                return False, "未找到错题卡"
        else:
            # 加入finished group
            if wrong_group:
                # total_len = len(wrong_group.split(";"))

                # add to review list (to do)
                if wrong_group == "okokok":
                    return True, True
                else:
                    return True, False
            else:
                return False, "未找到错题卡"
    except Exception as e:
        return False, str(e)

# def re_words(
#     payload,
#     **kwargs
# ):
#     return True, payload
#
#
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
            if record.loop >= record.current_loop:
                return True, "redo"
            else:
                # 执行finished
                return True, "finished"
        else:
            return False, "未找到record"
