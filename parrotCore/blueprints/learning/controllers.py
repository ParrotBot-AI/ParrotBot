from blueprints.learning.models import (
    Tasks,
    TaskAccounts,
    TaskFlows,
    Modules,
    VocabsLearning,
    VocabsLearningRecords,
    TaskFlowsConditions,
    StudyPulseRecords
)
from blueprints.account.models import (Accounts, Users)
from pprint import pprint
from configs.environment import DATABASE_SELECTION
from importlib import import_module

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath, iso_ts, get_today_midnight
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert, func, text
import json
from utils.redis_tools import RedisWrapper
import os
import sys

from configs.operation import DAILY_STUDY_TIME_TARGET, DAILY_STUDY_LOGIN_COUNT_TARGET, NON_MEMBER_VOCAB_GREEN_TIME, STUDY_LOOP

current_file_path = os.path.abspath(__file__)
parent_directory = os.path.dirname(current_file_path)
if parent_directory not in sys.path:
    sys.path.append(parent_directory)
import vocab_learning

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class VocabLearningController(crudController):

    def refuse_jump(self, account_id):
        redis = RedisWrapper('core_cache')
        cache_resp = redis.get(f'VocabsStatics:{account_id}')
        if cache_resp:
            if "refuse_skip" in cache_resp:
                cache_resp['refuse_skip'] = True
                redis.set(f'VocabsStatics:{account_id}', cache_resp, 7200)

        update_s = {
            "account_id": account_id,
            "refuse_skip": True
        }
        res, data = self._update(model=VocabsLearning, update_parameters=update_s, restrict_field="account_id")
        return res, data

    def jump_to_vocabs(self, account_id, category_id, exam_id=1):
        from blueprints.education.models import (VocabCategorys, VocabCategoryRelationships)
        redis = RedisWrapper('core_learning')
        cache = RedisWrapper('core_cache')
        with db_session('core') as session:
            record = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )
            if not record:
                return False, "未找到该用户"

            cate = record.current_category

            cate_r = (
                session.query(VocabCategorys)
                .filter(VocabCategorys.id == cate)
                .one_or_none()
            )
            records = (
                session.query(VocabCategorys)
                .filter(or_(VocabCategorys.id == cate, VocabCategorys.id == category_id))
                .all()
            )
            _r = -1
            c_id = None
            for r in records:
                if r.order > _r:
                    _r = r.order
                    c_id = r.id

            if c_id == cate:
                # 暂不支持往回跳
                return False, "不支持往回跳过词汇"
            else:
                records = (
                    session.query(VocabCategorys)
                    .filter(or_(VocabCategorys.exam_id == exam_id, VocabCategorys.exam_id == None))
                    .filter(VocabCategorys.order >= _r)
                    .all()
                )
                cate_ids = [x.id for x in records]

                words = (
                    session.query(VocabCategoryRelationships)
                    .filter(VocabCategoryRelationships.category_id.in_(cate_ids))
                    .all()
                )

                # 查看跳了多少词
                jump_words = (
                    session.query(VocabCategoryRelationships)
                    .join(VocabCategorys, VocabCategoryRelationships.category_id == VocabCategorys.id)
                    .filter(or_(VocabCategorys.exam_id == exam_id, VocabCategorys.exam_id == None))
                    .filter(and_(VocabCategorys.order < _r, VocabCategorys.order >= cate_r.order))
                    .all()
                )
                jump_words_len = len(jump_words)

                # 重构词表
                input_list = [x.word_id for x in words]
                in_process = redis.lrange(f"{record.in_process}")
                redis.list_pop(f"{record.in_process}", "l", len(in_process))
                today = redis.lrange(f"{record.today_learn}")
                redis.list_pop(f"{record.today_learn}", "l", len(today))

                if len(input_list) > 0:
                    import random
                    random.shuffle(input_list)
                    l = redis.list_push(f"{record.in_process}", *input_list, side="r")
                    for _ in range(record.amount if record.amount < len(input_list) else len(input_list)):
                        redis.list_move(f"{record.in_process}", f"{record.today_learn}")

                # print(f'input list: {len(input_list)}', 133)
                # print(f'in_process after jump: {len(redis.lrange(f"{record.in_process}"))}', 134)
                # print(f'today after jump: {len(redis.lrange(f"{record.today_learn}"))}', 135)

                # 更新user vocab 词汇:
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
                        Users.vocab_level: user_r.vocab_level + jump_words_len if user_r.vocab_level is not None else jump_words_len,
                        Users.last_update_time: datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                    })
                )

                record_update = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == account_id)
                    .update({
                        VocabsLearning.current_category: c_id,
                        VocabsLearning.is_skip_remind: None,
                        VocabsLearning.refuse_skip: None
                    })
                )

            try:
                session.commit()
                cache.delete(f"VocabsStatics:{account_id}")
                return True, "跳过成功"
            except Exception as e:
                session.rollback()
                return False, {str(e)}

    def reset_vocabs(self, account_id):
        from blueprints.education.models import (VocabCategorys, VocabCategoryRelationships)
        redis = RedisWrapper('core_learning')
        cache = RedisWrapper('core_cache')
        with db_session('core') as session:
            record = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )
            if not record:
                return False, "未找到该用户"

            redis.delete(f"{record.today_learn}")
            redis.delete(f"{record.in_process}")
            redis.delete(f"{record.unknown}")
            redis.delete(f"{record.finished}")
            redis.delete(f"{record.to_review}")
            redis.delete(f"{account_id}:wrong_group")

            new_cate = 1  # 默认从第一个category开始
            acc = (
                session.query(Accounts)
                .filter(Accounts.id == record.account_id)
                .one_or_none()
            )
            if acc:
                exam = acc.exam_id
                cate_records = (
                    session.query(VocabCategorys)
                    .filter(or_(VocabCategorys.exam_id == exam, VocabCategorys.exam_id == None))
                    .order_by(VocabCategorys.order.asc())
                    .all()
                )

                for r in cate_records:
                    words = (
                        session.query(VocabCategoryRelationships)
                        .filter(VocabCategoryRelationships.category_id == r.id)
                        .all()
                    )
                    input_list = [x.word_id for x in words]
                    if len(input_list) > 0:
                        import random
                        random.shuffle(input_list)
                        l = redis.list_push(f"{record.in_process}", *input_list, side="r")

                # 移动amount词汇到today里面
                for _ in range(record.amount):
                    redis.list_move(f"{record.in_process}", f"{record.today_learn}")

                update_parameters = dict(
                    current_category=new_cate,
                    is_skip_remind=None,
                    refuse_skip=None
                )
                default_dic = {
                    'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}

                update_ = (
                    session.query(VocabsLearning)
                    .filter(VocabsLearning.account_id == record.account_id)
                    .update({**update_parameters, **default_dic})
                )

                # 更新user vocab 词汇:
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
                        Users.vocab_level: 0,
                        Users.last_update_time: datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                    })
                )
            else:
                return False, "未知账户"

            try:
                session.commit()
                cache.delete(f"VocabsStatics:{account_id}")
                return True, "OK"
            except Exception as e:
                session.rollback()
                return False, str(e)

    def add_new_word_category(self, category_id):
        from blueprints.education.models import (VocabCategoryRelationships)
        redis = RedisWrapper('core_learning')
        with db_session('core') as session:
            records = (session.query(VocabsLearning).all())
            for record in records:
                in_process = redis.lrange(f"{record.in_process}")
                if len(in_process) > 0:
                    # redis.list_pop(f"{record.in_process}", "r", 335)
                    words = (
                        session.query(VocabCategoryRelationships)
                        .filter(VocabCategoryRelationships.category_id == category_id)
                        .all()
                    )
                    input_list = [x.word_id for x in words]
                    if len(input_list) > 0:
                        import random
                        random.shuffle(input_list)
                        l = redis.list_push(f"{record.in_process}", *input_list, side="r")
            return True, "更新成功"

    def create_new_vocab_tasks(self, account_id):
        s_l = []
        with db_session('core') as session:
            acc = (
                session.query(Accounts)
                .filter(Accounts.id == account_id)
                .one_or_none()
            )
            if acc:
                user_id = acc.user_id
                user = (
                    session.query(Users)
                    .filter(Users.id == user_id)
                    .one_or_none()
                )
                if user:
                    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                    compare_time = user.create_time.replace(tzinfo=timezone(timedelta(hours=8)))
                    if (user.user_plan != 0 and user.user_plan is not None) or (
                            now - compare_time).total_seconds() <= NON_MEMBER_VOCAB_GREEN_TIME:
                        new_task = dict(
                            account_id=account_id,
                            task_id=8,  # 背单词
                            is_active=1,
                            create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            loop=2,
                            current_loop=0,
                            level=0,
                            due_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).replace(hour=23, minute=59, second=59),
                            learning_type=1,
                        )
                        new_task_ = dict(
                            account_id=account_id,
                            task_id=9,  # 复习单词
                            is_active=1,
                            create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            loop=1,
                            level=0,
                            due_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).replace(hour=23, minute=59, second=59),
                            current_loop=0,
                            learning_type=1,
                        )
                        s_l.append(new_task)
                        s_l.append(new_task_)

            if len(s_l) > 0:
                session.execute(
                    insert(TaskAccounts),
                    s_l
                )
            else:
                return False, "账户Plan无创建权限."

            try:
                session.commit()
                return True, "创建用户任务成功."
            except Exception as e:
                return False, f"创建用户任务失败:{str(e)}."

    def create_vocabs_book(self, account_id):
        # 创建单词本
        from blueprints.education.models import VocabCategorys, VocabCategoryRelationships
        redis = RedisWrapper('core_learning')
        with db_session('core') as session:
            record = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )
            if not record:
                return False, "未找打账户单词"
            else:
                cate = record.current_category
                in_process = redis.get(f"{record.in_process}")
                if not in_process and not cate:
                    # 新用户，生成单词表
                    new_cate = 1  # 默认从第一个category开始
                    acc = (
                        session.query(Accounts)
                        .filter(Accounts.id == record.account_id)
                        .one_or_none()
                    )
                    if acc:
                        exam = acc.exam_id
                        cate_records = (
                            session.query(VocabCategorys)
                            .filter(or_(VocabCategorys.exam_id == exam, VocabCategorys.exam_id == None))
                            .order_by(VocabCategorys.order.asc())
                            .all()
                        )

                        for r in cate_records:
                            words = (
                                session.query(VocabCategoryRelationships)
                                .filter(VocabCategoryRelationships.category_id == r.id)
                                .all()
                            )
                            input_list = [x.word_id for x in words]
                            if len(input_list) > 0:
                                import random
                                random.shuffle(input_list)
                                l = redis.list_push(f"{record.in_process}", *input_list, side="r")

                        # 移动amount词汇到today里面
                        for _ in range(record.amount):
                            redis.list_move(f"{record.in_process}", f"{record.today_learn}")

                        update_parameters = dict(
                            current_category=new_cate
                        )
                        default_dic = {
                            'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}
                        update_ = (
                            session.query(VocabsLearning)
                            .filter(VocabsLearning.account_id == record.account_id)
                            .update({**update_parameters, **default_dic})
                        )
                    else:
                        pass
                else:
                    # 老用户，生成明日表
                    # 1. 按照amount,补齐今日的新表
                    today_left = redis.lrange(f"{record.today_learn}")
                    add_amount = record.amount - len(today_left)
                    l = redis.lrange(f"{record.in_process}")
                    if len(l) >= add_amount:
                        for _ in range(add_amount):
                            redis.list_move(f"{record.in_process}", f"{record.today_learn}")
                    else:
                        for _ in range(len(l)):
                            redis.list_move(f"{record.in_process}", f"{record.today_learn}")
                    # 2. 把昨天错误的加入 to_review
                    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                    start_of_today = datetime(now.year, now.month, now.day)
                    start_of_yesterday = start_of_today - timedelta(days=1)
                    words_records = (
                        session.query(VocabsLearningRecords.wrong_word_id)
                        .filter(VocabsLearningRecords.time > start_of_yesterday)
                        .filter(VocabsLearningRecords.time < start_of_today)
                        .filter(VocabsLearningRecords.wrong_word_id.is_not(None))
                        .all()
                    )
                    if len(words_records) > 0:
                        redis.list_push(f"{record.to_review}", *list(set([x.wrong_word_id for x in words_records])),
                                        side="r")

                    # 3. 更新statis
                    default_dic = {
                        'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}

                    update_parameters = dict(
                        last_day_review=record.today_day_review,
                        last_day_study=record.today_day_study,
                        today_day_study=0,
                        today_day_review=0,
                    )
                    update_ = (
                        session.query(VocabsLearning)
                        .filter(VocabsLearning.account_id == record.account_id)
                        .update({**update_parameters, **default_dic})
                    )

            try:
                session.commit()
                return True, "OK"
            except Exception as e:
                session.rollback()
                return False, str(e)

    def fetch_vocabs_level(self, account_id, exam_id=None):
        with db_session('core') as session:
            # 查找对应的exam
            if exam_id is None:
                account = (
                    session.query(Accounts)
                    .filter(Accounts.id == account_id)
                    .one_or_none()
                )
                if account:
                    exam_id = account.exam_id
                else:
                    return False, "账户"

            vocab_account = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )
            if not vocab_account:
                return False, "账户单词本未找到"

            current_cate = vocab_account.current_category
            if current_cate:
                redis = RedisWrapper('core_learning')
                number_to_finish = len(redis.lrange(f"{vocab_account.in_process}"))
                number_today = len(redis.lrange(f"{vocab_account.today_learn}"))

                # 查找Category对应条数
                raw_sql = text(f"""
                SELECT
                VocabsCategorys.id,
                VocabsCategorys.name,
                VocabsCategorys.`order`,
                S.counts
                FROM VocabsCategorys
                JOIN (
                SELECT VCR.category_id, COUNT(VCR.category_id) as counts FROM VocabCategoryRelationships VCR
                GROUP BY category_id
                ) S ON VocabsCategorys.id = S.category_id
                WHERE VocabsCategorys.exam_id = {exam_id} or VocabsCategorys.exam_id IS NULL
                ORDER BY `order`;
                """)
                results = session.execute(raw_sql).fetchall()

                # 逻辑就是总的需要背的，减去还需要背的，就是这个阶段背了的单词数
                # 无法找finished里面的，因为用户还可以跳词汇category
                total_amount = 0
                level_total = 0
                level_books = []
                for r in results:
                    if current_cate <= r.id:
                        total_amount += r.counts
                    if current_cate == r.id:
                        level_total = r.counts

                    level_books.append(dict(
                        id=r.id,
                        name=r.name,
                        order=r.order,
                        counts=r.counts
                    ))
                print(total_amount, number_to_finish, number_today, 520)
                at_level = total_amount - (number_to_finish + number_today)

                # 响应结果
                resp = {
                    "current_level": current_cate,
                    "level_status": at_level,
                    "level_total": level_total,
                    "level_book": level_books
                }
                return True, resp
            else:
                return False, "词表未生成"

    def fetch_past_5_days_list(self, t_interval, account_id):
        now_cst = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d')
        current_date_cst = now_cst
        date_series_sql_parts = [f"UNION ALL SELECT '{current_date_cst}' - INTERVAL {i} DAY\n" for i in range(t_interval)]
        date_series_sql = " ".join(date_series_sql_parts)
        with db_session('core') as session:
            # date_series_sql = " ".join(
            #     [f"UNION ALL SELECT CURDATE() - INTERVAL {i} DAY\n" for i in range(1, t_interval)])
            raw_sql = text(f"""
            SELECT
              DateSeries.day,
              SUM(Data.wrong_word) AS w_c,
              SUM(Data.correct_word) AS c_c
            FROM (
              SELECT '{current_date_cst}' as 'day'
              {date_series_sql}
            ) DateSeries
            LEFT JOIN (
              SELECT
                DATE(time) AS day,
                wrong_word_id IS NOT NULL AS wrong_word,
                correct_word_id IS NOT NULL AS correct_word
              FROM VocabsLearningRecords
              WHERE account_id = {account_id}
                AND time >= '{current_date_cst}' - INTERVAL {t_interval - 1} DAY
            ) AS Data ON DateSeries.day = Data.day
            GROUP BY DateSeries.day
            ORDER BY DateSeries.day ASC;
            """)

            # Execute the raw SQL query
            return session.execute(raw_sql).fetchall()

    def fetch_account_vocab(self, account_id):
        redis = RedisWrapper('core_cache')
        cache_resp = redis.get(f'VocabsStatics:{account_id}')
        if cache_resp:
            return True, cache_resp

        with db_session('core') as session:
            resp = {}
            account = (
                session.query(Accounts)
                .filter(Accounts.id == account_id)
                .one_or_none()
            )
            if not account:
                return False, "未找到该账户"

            record = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )

            if record:
                user = (
                    session.query(Users)
                    .filter(Users.id == account.user_id)
                    .one_or_none()
                )
                if user:
                    resp['vocab'] = user.vocab_level if user.vocab_level is not None else 0
                    resp['last_day_review'] = record.last_day_review
                    resp['last_day_study'] = record.last_day_study
                    resp['today_day_study'] = record.today_day_study
                    resp['today_day_review'] = record.today_day_review
                    resp['total_study'] = record.total_study
                    resp['total_review'] = record.total_review
                    resp['is_skip_remind'] = record.is_skip_remind
                    resp['refuse_skip'] = record.refuse_skip

                    # 搜索过去5天的正确的与错误的
                    results = self.fetch_past_5_days_list(t_interval=5, account_id=account_id)
                    s_l = {}
                    for result in results:
                        s_l[result.day] = {}
                        s_l[result.day]['wrong_words'] = int(result.w_c) if result.w_c else 0,
                        s_l[result.day]['correct_words'] = int(result.c_c) if result.c_c else 0,

                    resp['series'] = s_l
                    res, data = self.fetch_vocabs_level(account_id, account.exam_id)
                    if res:
                        resp['status_book'] = data

                    # 缓存
                    redis.set(f'VocabsStatics:{account_id}', resp, 7200)

                    return True, resp
                else:
                    return False, "未找到该用户"
            else:
                return False, "未找到该账号单词"

    def init_tasks(self, user_id):
        user = self._retrieve(model=Users, restrict_field='user_id', restrict_value=user_id)
        index_id = s.serialize_dic(user, self.default_not_show)['id']
        with db_session('core') as session:
            accs = (
                session.query(Accounts)
                .filter(Accounts.user_id == index_id)
                .all()
            )
            accounts_ids = [record.id for record in accs]
            for each_a in accounts_ids:
                self.create_new_vocab_tasks(each_a)

    def init_vocabs_books(self, user_id):
        from blueprints.education.models import VocabCategorys, VocabCategoryRelationships
        redis = RedisWrapper('core_learning')
        user = self._retrieve(model=Users, restrict_field='user_id', restrict_value=user_id)
        index_id = s.serialize_dic(user, self.default_not_show)['id']

        with db_session('core') as session:
            accs = (
                session.query(Accounts)
                .filter(Accounts.user_id == index_id)
                .all()
            )
            accounts_ids = [record.id for record in accs]
            records = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id.in_(accounts_ids))
                .all()
            )
            for record in records:
                cate = record.current_category
                in_process = redis.get(f"{record.in_process}")
                if not in_process and not cate:
                    # 新用户，生成单词表
                    new_cate = 1  # 默认从第一个category开始
                    acc = (
                        session.query(Accounts)
                        .filter(Accounts.id == record.account_id)
                        .one_or_none()
                    )
                    if acc:
                        exam = acc.exam_id
                        cate_records = (
                            session.query(VocabCategorys)
                            .filter(or_(VocabCategorys.exam_id == exam, VocabCategorys.exam_id == None))
                            .order_by(VocabCategorys.order.asc())
                            .all()
                        )

                        for r in cate_records:
                            words = (
                                session.query(VocabCategoryRelationships)
                                .filter(VocabCategoryRelationships.category_id == r.id)
                                .all()
                            )
                            input_list = [x.word_id for x in words]
                            if len(input_list) > 0:
                                import random
                                random.shuffle(input_list)
                                l = redis.list_push(f"{record.in_process}", *input_list, side="r")

                        # 移动amount词汇到today里面
                        for _ in range(record.amount):
                            redis.list_move(f"{record.in_process}", f"{record.today_learn}")

                        update_parameters = dict(
                            current_category=new_cate
                        )
                        default_dic = {
                            'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}
                        update_ = (
                            session.query(VocabsLearning)
                            .filter(VocabsLearning.account_id == record.account_id)
                            .update({**update_parameters, **default_dic})
                        )

                        # 注册今日单词任务（初始化，用户可获得一天的任务s）:
                        s_l = []

                        # 如果今天没有单词任务，创建
                        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                        start_of_today = datetime(now.year, now.month, now.day)
                        tasks = (
                            session.query(TaskAccounts)
                            .filter(or_(TaskAccounts.task_id == 8, TaskAccounts.task_id == 9))
                            .filter(TaskAccounts.account_id == record.account_id)
                            .filter(TaskAccounts.create_time > start_of_today)
                            .all()
                        )
                        if len(tasks) == 0:
                            # 添加任务
                            new_task = dict(
                                account_id=record.account_id,
                                task_id=8,  # 背单词
                                is_active=1,
                                create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                last_update_time=datetime.now(timezone.utc).astimezone(
                                    timezone(timedelta(hours=8))),
                                loop=STUDY_LOOP,
                                current_loop=1,
                                learning_type=1,
                            )
                            new_task_ = dict(
                                account_id=record.account_id,
                                task_id=9,  # 复习单词
                                is_active=1,
                                create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                last_update_time=datetime.now(timezone.utc).astimezone(
                                    timezone(timedelta(hours=8))),
                                loop=STUDY_LOOP,
                                current_loop=1,
                                learning_type=1,
                            )
                            s_l.append(new_task)
                            s_l.append(new_task_)

                        if len(s_l) > 0:
                            session.execute(
                                insert(TaskAccounts),
                                s_l
                            )
                    else:
                        pass

            try:
                session.commit()
                return True, 'OK.'
            except Exception as e:
                return False, "创建账户单词词库成功."

    def init_vocabs_learnings(self, user_id):
        user = self._retrieve(model=Users, restrict_field='user_id', restrict_value=user_id)
        index_id = s.serialize_dic(user, self.default_not_show)['id']

        with db_session('core') as session:
            records = (
                session.query(Accounts)
                .filter(Accounts.user_id == index_id)
                .all()
            )
            accounts_ids = [record.id for record in records]
            for account_id in accounts_ids:
                new = dict(
                    account_id=account_id,
                    in_process=f'{account_id}:in_process',
                    finished=f'{account_id}:finished',
                    to_review=f'{account_id}:to_review',
                    unknown=f'{account_id}:unknown',
                    today_learn=f'{account_id}:today',
                    amount=200
                )
                default_dic = {
                    'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                    'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                }
                merged_dict = {**new, **default_dic}
                n_record = VocabsLearning(**merged_dict)
                session.add(n_record)

            try:
                session.commit()
                return True, 'OK.'
            except Exception as e:
                return False, "创建账户单词学习失败."


class StudyPulseController(crudController):
    # 打卡
    def add_pulse_time(self, account_id, time_length):
        add = {
            "account_id": account_id,
            "time_length": time_length if time_length is not None else None,
            "counter": 1
        }
        return self._create(model=StudyPulseRecords, create_params=add)

    def get_pulse_check_information(self, account_id):
        """
        查看打卡的信息
        1.查看登录次数（后期不会用）
        2.查看学习时间 (过去7天）
        """
        counter_target = DAILY_STUDY_LOGIN_COUNT_TARGET
        time_target = DAILY_STUDY_TIME_TARGET

        def get_weekday(date_str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            # 返回星期几的整数值和对应的星期字符串（例如，'Monday'）
            return date_obj.strftime('%A')

        end_date = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()
        start_date = end_date - timedelta(days=7 - 1)
        # 生成日期范围
        date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
        with db_session('core') as session:
            # 查看过去7天登录次数和学习时间：
            records = (
                session.query(
                    func.date(StudyPulseRecords.create_time).label('date'),
                    func.sum(StudyPulseRecords.counter).label('count'),
                    func.sum(StudyPulseRecords.time_length).label('study_time')
                )
                .filter(StudyPulseRecords.account_id == account_id)
                .filter(and_(
                    StudyPulseRecords.create_time >= start_date,
                    StudyPulseRecords.create_time <= end_date))
                .group_by(
                    func.date(StudyPulseRecords.create_time)
                )
                .order_by(
                    func.date(StudyPulseRecords.create_time)
                )
                .all()
            )
            date_dic = []
            # 将查询结果转换为字典，便于快速查找
            results_dict = {result[0]: result for result in records}
            new = {}

            for date in date_range:
                if date in results_dict:
                    record = {
                        "date": date.strftime('%Y-%m-%d'),
                        "week_day": get_weekday(date.strftime('%Y-%m-%d')),
                        "login_count": int(results_dict[date][1]) if results_dict[date][1] is not None else 0,
                        "study_time": int(results_dict[date][2]) if results_dict[date][2] is not None else 0
                    }
                else:
                    record = {
                        "date": date.strftime('%Y-%m-%d'),
                        "week_day": get_weekday(date.strftime('%Y-%m-%d')),
                        "login_count": 0,
                        "study_time": 0
                    }
                date_dic.append(record)
                new[record["date"]] = record

            # 打开状态：
            status = []
            remaining_week = [end_date + timedelta(days=i) for i in range(7 - end_date.weekday())]
            sorted_week = sorted(remaining_week, key=lambda x: x.weekday())

            for date in sorted_week:
                if date.strftime('%Y-%m-%d') in new:
                    record = {
                        "date": date.strftime('%Y-%m-%d'),
                        "week_day": get_weekday(date.strftime('%Y-%m-%d')),
                        "count_process": new[date.strftime('%Y-%m-%d')]['login_count'],
                        "count_target": counter_target,
                        "study_time": new[date.strftime('%Y-%m-%d')]['study_time'],
                        "time_target": time_target,
                        "lock": False
                    }
                else:
                    record = {
                        "date": date.strftime('%Y-%m-%d'),
                        "week_day": get_weekday(date.strftime('%Y-%m-%d')),
                        "count_process": 0,
                        "count_target": counter_target,
                        "study_time": 0,
                        "time_target": time_target,
                        "lock": True
                    }
                status.append(record)

            response = {
                "current": end_date.strftime('%Y-%m-%d'),
                "charts": date_dic,
                "daka": status
            }
            return True, response


class TaskController(crudController):
    def fetch_account_tasks(self, account_id, after_time=None, active=None, type=None, is_complete=None):
        with db_session('core') as session:
            query = session.query(TaskAccounts).filter(TaskAccounts.account_id == account_id)
            if active is not None:
                query = query.filter(TaskAccounts.is_active == active)
            if after_time is not None:
                query = query.filter(TaskAccounts.create_time > after_time)
            if type is not None:
                query = query.filter(TaskAccounts.learning_type == type)

            if is_complete is not None:
                query = query.filter(TaskAccounts.is_complete == is_complete)  # 获取还未完成的
            tasks = query.all()
            resp = []
            for task in tasks:
                tas = {}
                record = (
                    session.query(Tasks)
                    .filter(Tasks.id == task.task_id)
                    .one_or_none()
                )
                if record:
                    tas['task_account_id'] = task.id
                    tas['task_name'] = record.task_name
                    tas['task_id'] = record.id
                    tas['order'] = record.order
                    tas['status'] = task.status
                    tas['is_complete'] = task.is_complete
                    tas['complete_p'] = task.complete_percentage
                    resp.append(tas)
                else:
                    return False, "未找到相关任务"

            return True, resp

    def search_next_chain(self, response: dict, payload: dict, **kwargs):
        chain = response['chain']
        current_m = response['current_m']
        current_task = response['current_task']

        if current_task['out_function']:
            info = json.loads(current_task['out_function'])
            # out function should be a json has three attributes:
            # modules, method, payload
            module, method, payload_ = info['module'], info['method'], info['payload']
            # 运行下一步返回参数函数
            module = import_module(module)
            function = getattr(module, method)
            print(function.__name__)
            input = response.copy()
            input['payload'] = payload
            resp, data = function(**input)
            if resp:
                # to do 更新 start data
                tasks = [item for item in chain if item['from_module_id'] == current_m]
                next_task = None
                if len(tasks) > 1:
                    for task in tasks:
                        result = json.loads(task['result'])
                        type, value, re = result['type'], result['value'], result['r']
                        # type_function = globals()[type]
                        expression = f"{data} {re} {value}"
                        if eval(expression):
                            next_task = task
                            break
                    return True, next_task
                else:
                    return True, tasks[0]
            else:
                return False, data
        else:
            return False, "开始任务失败，任务链条件函数获取失败"

    def fetch_module_chains_conditions(self, task_account_id):
        with db_session('core') as session:
            records = (
                session.query(
                    TaskFlows.from_module_id,
                    TaskFlows.to_module_id,
                    TaskFlows.condition_id,
                    TaskFlows.result,
                    TaskFlowsConditions.in_function,
                    TaskFlowsConditions.out_function,
                    TaskFlowsConditions.condition
                )
                .join(Tasks, Tasks.id == TaskFlows.task_id)
                .join(TaskAccounts, Tasks.id == TaskAccounts.task_id)
                .join(TaskFlowsConditions, TaskFlows.condition_id == TaskFlowsConditions.id)
                .filter(TaskAccounts.id == task_account_id)
                .filter(TaskFlows.is_active == 1)
                .filter(TaskFlowsConditions.is_active == 1)
                .all()
            )
            resp = []
            for record in records:
                dic = dict(
                    from_module_id=record.from_module_id,
                    to_module_id=record.to_module_id,
                    condition_id=record.condition_id,
                    result=record.result,
                    in_function=record.in_function,
                    out_function=record.out_function,
                    condition=record.condition
                )
                resp.append(dic)
            return True, resp

    def fetch_module_chains(self, account_id, task_id, module_id=None):
        # 如果不传module，将会返回整条chain
        # 如果传module，则会返回下一条
        # 2次搜索
        with db_session('core') as session:
            if module_id:
                task = (
                    session.query(TaskFlows)
                    .filter(TaskFlows.is_active == True)
                    .filter(TaskFlows.task_id == task_id)
                    .filter(TaskFlows.from_module_id == module_id)
                    .one_or_none()
                )
                if task:
                    return True, s.serialize_dic(task, self.default_not_show)
            else:
                # 一并返回conditions
                tasks = (
                    session.query(TaskFlows)
                    .filter(TaskFlows.is_active == True)
                    .filter(TaskFlows.task_id == task_id)
                    .all()
                )
                if tasks:
                    for task in tasks:
                        if task.from_module_id is None:
                            first_module = task.to_module_id
                            id = task.id

                    r = {}
                    l = s.serialize_list(tasks, self.default_not_show)
                    for item_ in l:
                        r[item_['id']] = item_

                    response = {
                        "current_m": first_module,
                        "task_flow_id": id,
                        "chain": r
                    }

                    # session.close()
                    return True, response
                else:
                    return False, "未找到任务链"

    def start_task(self, task_account_id):
        # 获取taskAccount (看有几个loop, current_loop)
        # 生成一个task_chain (最好是graph格式) ->缓存
        # 找到第一个module
        # 生成第一个module所需的数据， 返回

        # 运用缓存，减少读写: 2次搜索
        res = {}
        cache = {}
        with db_session('core') as session:
            record = (
                session.query(TaskAccounts)
                .filter(TaskAccounts.id == task_account_id)
                .one_or_none()
            )
            if record:
                task = (
                    session.query(Tasks)
                    .filter(Tasks.id == record.task_id)
                    .one_or_none()
                )
                res['account_id'] = record.account_id
                res['task_name'] = task.task_name
                res['task_id'] = record.task_id
                res['loop'] = record.loop
                res['current_loop'] = record.current_loop
                res['task_account_id'] = task_account_id

                if record.loop <= record.current_loop:
                    return False, '任务已经完成'

                now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                start_of_today = datetime(now.year, now.month, now.day)
                if record.create_time < start_of_today or record.due_time < now:
                    return False, '任务已过期'

                if res['task_name'] == "复习旧单词":
                    # 查找今日背诵单词是否完成:
                    learn_records = (
                        session.query(TaskAccounts)
                        .filter(TaskAccounts.task_id == 8)
                        .filter(TaskAccounts.account_id == record.account_id)
                        .filter(TaskAccounts.create_time > start_of_today)
                        .all()
                    )
                    for learn_record in learn_records:
                        if not learn_record.is_complete == 1:
                            return False, '今日还有未完成的单词学习任务'

        current_task, pointer = None, None
        if res != {}:
            resp, data = self.fetch_module_chains_conditions(task_account_id=task_account_id)
            if resp:
                res['chain'] = data
                current_task = [item for item in data if item['from_module_id'] is None][0]
            else:
                return False, "开始任务失败，任务链获取失败"

        res['current_m'] = current_task['to_module_id']
        res['current_task'] = current_task

        try:
            if current_task['in_function']:
                info = json.loads(current_task['in_function'])
                # out function should be a json has three attributes:
                # modules, method, payload
                module, method, payload = info['module'], info['method'], info['payload']
                # 运行下一步返回参数函数
                module = import_module(module)
                function = getattr(module, method)
                print(function.__name__)
                resp, data, return_c = function(record.account_id)
                if resp:
                    # cache the chain
                    redis = RedisWrapper('core_cache')
                    redis.set(f"TaskAccount:{task_account_id}", res, ex=1 * 24 * 60 * 60)  # 一天后自动过期
                    if return_c:
                        # to do 更新 start time
                        u_record = (
                            session.query(TaskAccounts)
                            .filter(TaskAccounts.id == task_account_id)
                            .update({
                                TaskAccounts.started_time: datetime.now(timezone.utc).astimezone(
                                    timezone(timedelta(hours=8))),
                                TaskAccounts.status:1
                            })
                        )
                        try:
                            session.commit()
                            return True, {
                                "payload": data
                            }
                        except Exception as e:
                            return False, f"{str(e)}."
                else:
                    return False, data

        except Exception as e:
            return False, f"开始任务失败, 条件任务函数运行失败 {e}"

    def send_module_outcome(self, next_task, task_account_id, response):
        # 2次搜索， 2次function
        response['current_task'] = next_task
        response['current_m'] = next_task['to_module_id']
        try:
            if next_task['in_function']:
                info = json.loads(next_task['in_function'])
                # out function should be a json has three attributes:
                # modules, method, payload
                module, method, payload = info['module'], info['method'], info['payload']
                # 运行下一步返回参数函数
                module = import_module(module)
                function = getattr(module, method)
                print(function.__name__)
                resp, data, return_c = function(**response)
                if resp:
                    response['condition_id'] = next_task['condition_id']

                    if return_c:
                        redis = RedisWrapper('core_cache')
                        redis.set(f"TaskAccount:{task_account_id}", response, ex=1 * 24 * 60 * 60)  # 一天后自动过期
                        return True, {
                            "payload": data
                        }

                    else:
                        # out_function
                        if next_task['out_function']:
                            info = json.loads(next_task['out_function'])
                            module, method, payload = info['module'], info['method'], info['payload']
                            # 运行下一步返回参数函数
                            module = import_module(module)
                            function = getattr(module, method)
                            print(function.__name__)
                            resp, data = function(**response)
                            if resp:
                                response['condition_id'] = next_task['condition_id']

                                # redo the loop
                                if data == "redo":
                                    return self.start_task(task_account_id)

                                # finished the loop
                                elif data == "finished":
                                    return True, data
                                else:
                                    return True, data
                            else:
                                return False, data

                        else:
                            return False, f"开始任务失败, 条件任务无法找到"

                else:
                    return False, data

            else:
                return False, f"开始任务失败, 条件任务无法找到"
        except Exception as e:
            return False, f"开始任务失败, 条件任务函数运行失败 {e}"

    def rec_module_outcome(
            self,
            task_account_id,
            payload,
            **kwargs):

        with db_session('core') as session:
            record = (
                session.query(TaskAccounts)
                .filter(TaskAccounts.id == task_account_id)
                .one_or_none()
            )
            if not record:
                return False, '找不到任务信息'
            if record.loop <= record.current_loop:
                return False, '任务已经完成'

            now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            start_of_today = datetime(now.year, now.month, now.day)
            if record.create_time < start_of_today:
                return False, '任务已过期'

        redis = RedisWrapper('core_cache')
        task_flow = redis.get(f"TaskAccount:{task_account_id}")
        if task_flow:
            resp, next_task = self.search_next_chain(response=task_flow, payload=payload['payload'])
            if resp:
                return self.send_module_outcome(next_task, task_account_id, task_flow)
            else:
                return False, next_task
        else:
            with db_session('core') as session:
                record = (
                    session.query(TaskAccounts)
                    .filter(TaskAccounts.id == task_account_id)
                    .one_or_none()
                )
                if not record:
                    return False, '找不到任务信息'
                if record.loop <= record.current_loop:
                    return False, '任务已经完成'

                now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                start_of_today = datetime(now.year, now.month, now.day)
                if record.create_time < start_of_today:
                    return False, '任务已过期'

                return False, '学习失败'


if __name__ == "__main__":
    account_id = 37
    pprint(VocabLearningController().create_new_vocab_tasks(account_id=27))
    # pprint(VocabLearningController().fetch_account_vocab(27))
    # pprint(VocabLearningController().reset_vocabs(account_id=37))
    # pprint(VocabLearningController().jump_to_vocabs(account_id=37, category_id=2))
    # pprint(VocabLearningController().fetch_account_vocab(37))
    # pprint(StudyPulseController().get_pulse_check_information(account_id=27))

    # pprint(TaskController().fetch_account_tasks(account_id=account_id, after_time=get_today_midnight(), active=True))
    # today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    # time = datetime(today.year, today.month, today.day, 0, 0)
    # res, data = TaskController().fetch_account_tasks(
    #     account_id=account_id,
    #     after_time=time,
    #     type=1,
    #     is_complete=0,
    # )
    # pprint(data)

    # pprint(TaskController().start_task(task_account_id=154))

    # 背单词
    # 1.先用5个
    # payload = {'payload': {'word_id': 37473, 'word': 'grind', 'stem': ['n. 槽', 'v. 磨（碎）；磨利', 'v. 刮；擦 n. 刮；擦伤；擦痕', 'v. 掘，挖；采掘'], 'word_ids': [40069, 37473, 37353, 36791], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 2.
    # payload = {'payload': {'word_id': 34679, 'word': 'counsel', 'stem': ['n. 律师， 代理人', 'n. 律师；法学家', 'v. 忠告，建议', 'n. 律师， 法律顾问'], 'word_ids': [38497, 35699, 34679, 38247], 'correct_answer': [0, 0, 1, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 3.
    # payload = {'payload': {'word_id': 39818, 'word': 'environmental', 'stem': ['adj. 生态学的', 'adj. 环境的，环境产生的', 'n. 污染', 'n. 生态学；个体生态学'], 'word_ids': [38576, 39818, 37402, 39478], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 4.
    # payload = {'payload': {'word_id': 37716, 'word': 'feeble', 'stem': ['adj. 哀婉动人的；可怜的', 'adj. 不幸的', '瘦的；（土地）不毛的；思想贫乏的', 'adj. 虚弱的；微弱的'], 'word_ids': [40159, 40079, 40882, 37716], 'correct_answer': [0, 0, 0, 1], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 5.
    # payload = {'payload': {'word_id': 35851, 'word': 'spark', 'stem': ['v. 引燃，着火', 'n. 火花，火星', 'n. 刺激物 v. 刺激', 'n. 推动， 促进， 刺激； 推动力'], 'word_ids': [39197, 35851, 37697, 40649], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    ## model fetch
    # payload = {'payload': {'endpoint': 'gpt-endpint', 'method': 'sse', 'api_key': 'key', 'send': {'counsel': 'v. 忠告，建议', 'spark': 'n. 火花，火星', 'grind': 'v. 磨（碎）；磨利', 'feeble': 'adj. 虚弱的；微弱的', 'environmental': 'adj. 环境的，环境产生的'}, 'response': '建议(counsel), 卸下(grind), 虚弱(feeble), 环境(environmental)', 'execute': True, 'target': ['execute', 'response']}}

    # 开始复习错误词汇
    # 1. False
    # payload = {'payload': {'word_id': 37473, 'word': 'grind', 'stem': ['n. 槽', 'v. 磨（碎）；磨利', 'v. 刮；擦 n. 刮；擦伤；擦痕', 'v. 掘，挖；采掘'], 'word_ids': [40069, 37473, 37353, 36791], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study'], 'hint': ', 卸下(grind'}}
    # 2. True
    # payload = {'payload': {'word_id': 39818, 'word': 'environmental', 'stem': ['adj. 生态学的', 'adj. 环境的，环境产生的', 'n. 污染', 'n. 生态学；个体生态学'], 'word_ids': [38576, 39818, 37402, 39478], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 1, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study'], 'hint': ', 环境(environmental'}}
    # 3. True
    # payload = {'payload': {'word_id': 34679, 'word': 'counsel', 'stem': ['n. 律师， 代理人', 'n. 律师；法学家', 'v. 忠告，建议', 'n. 律师， 法律顾问'], 'word_ids': [38497, 35699, 34679, 38247], 'correct_answer': [0, 0, 1, 0], 'answer': [0, 0, 1, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study'], 'hint': '建议(counsel'}}
    #
    # print(flow.rec_module_outcome(task_account_id=15, payload=payload)[1])

    # 复习单词
    # flow = TaskController()
    # resp, payload = flow.start_task(task_account_id=5)
    # print(payload)
    # 1. F
    # payload = {'payload': {'word_id': 37473, 'word': 'grind', 'stem': ['n. 槽', 'v. 磨（碎）；磨利', 'v. 刮；擦 n. 刮；擦伤；擦痕', 'v. 掘，挖；采掘'], 'word_ids': [40069, 37473, 37353, 36791], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 2. T
    # payload = {'payload': {'word_id': 34679, 'word': 'counsel', 'stem': ['n. 律师， 代理人', 'n. 律师；法学家', 'v. 忠告，建议', 'n. 律师， 法律顾问'], 'word_ids': [38497, 35699, 34679, 38247], 'correct_answer': [0, 0, 1, 0], 'answer': [0, 0, 1, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 3. T
    # payload = {'payload': {'word_id': 39818, 'word': 'environmental', 'stem': ['adj. 生态学的', 'adj. 环境的，环境产生的', 'n. 污染', 'n. 生态学；个体生态学'], 'word_ids': [38576, 39818, 37402, 39478], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 1, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 4 . F
    # payload = {'payload': {'word_id': 37716, 'word': 'feeble', 'stem': ['adj. 哀婉动人的；可怜的', 'adj. 不幸的', '瘦的；（土地）不毛的；思想贫乏的', 'adj. 虚弱的；微弱的'], 'word_ids': [40159, 40079, 40882, 37716], 'correct_answer': [0, 0, 0, 1], 'answer': [1, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 5. T
    # payload = {'payload': {'word_id': 35851, 'word': 'spark', 'stem': ['v. 引燃，着火', 'n. 火花，火星', 'n. 刺激物 v. 刺激', 'n. 推动， 促进， 刺激； 推动力'], 'word_ids': [39197, 35851, 37697, 40649], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 1, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 6. F
    # payload = {'payload': {'word_id': 34679, 'word': 'counsel', 'stem': ['n. 律师， 代理人', 'n. 律师；法学家', 'v. 忠告，建议', 'n. 律师， 法律顾问'], 'word_ids': [38497, 35699, 34679, 38247], 'correct_answer': [0, 0, 1, 0], 'answer': [0, 0, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 7. T
    # payload = {'payload': {'word_id': 37473, 'word': 'grind', 'stem': ['n. 槽', 'v. 磨（碎）；磨利', 'v. 刮；擦 n. 刮；擦伤；擦痕', 'v. 掘，挖；采掘'], 'word_ids': [40069, 37473, 37353, 36791], 'correct_answer': [0, 1, 0, 0], 'answer': [0, 1, 0, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 8. T
    # payload = {'payload': {'word_id': 37716, 'word': 'feeble', 'stem': ['adj. 哀婉动人的；可怜的', 'adj. 不幸的', '瘦的；（土地）不毛的；思想贫乏的', 'adj. 虚弱的；微弱的'], 'word_ids': [40159, 40079, 40882, 37716], 'correct_answer': [0, 0, 0, 1], 'answer': [0, 0, 0, 1], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # 9. T
    # payload = {'payload': {'word_id': 34679, 'word': 'counsel', 'stem': ['n. 律师， 代理人', 'n. 律师；法学家', 'v. 忠告，建议', 'n. 律师， 法律顾问'], 'word_ids': [38497, 35699, 34679, 38247], 'correct_answer': [0, 0, 1, 0], 'answer': [0, 0, 1, 0], 'unknown': False, 'study': False, 'target': ['answer', 'unknown', 'study']}}
    # print(flow.rec_module_outcome(task_account_id=12, payload=payload)[1])
