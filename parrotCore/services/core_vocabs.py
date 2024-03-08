from blueprints.learning.controllers import VocabLearningController
from blueprints.learning.models import (
    Tasks,
    TaskAccounts,
    TaskFlows,
    Modules,
    VocabsLearning,
    VocabsLearningRecords,
    TaskFlowsConditions
)
from blueprints.account.models import (
    Accounts,
    Users
)
from blueprints.education.models import (
    VocabBase,
    VocabCategoryRelationships,
    VocabCategorys
)
from sqlalchemy import select, func, Date, cast, and_, text, literal_column, case
from datetime import datetime, timedelta
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
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert
import json
from utils.redis_tools import RedisWrapper

logger = get_general_logger('vocab_log', path=abspath('logs', 'vocab_service'))


class VocabsService:
    # 每日定时任务，单词本管理
    # 单词本保持右进左出

    def __init__(self):
        pass

    def check_accounts_words_book(self):
        # 检查是否存在单词本，如果不存在，添加单词本
        with db_session('core') as session:
            query = select(Accounts.id).outerjoin(VocabsLearning, Accounts.id == VocabsLearning.account_id).where(
                VocabsLearning.account_id == None)
            result = session.execute(query)

            # Fetch and print results
            missing_accounts = [x.id for x in result]
            s_l = []
            if len(missing_accounts) > 0:
                for account_id in missing_accounts:
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
                    s_l.append(merged_dict)

                session.execute(
                    insert(VocabsLearning),
                    s_l
                )

                try:
                    session.commit()
                    return True, logger.info("同步账户单词学习成功.")
                except Exception as e:
                    return False, logger.info(f"同步账户单词学习失败.")
            else:
                return True, logger.info("账户与词本保持一致.")

    def generate_new_words(self):
        redis = RedisWrapper('core_learning')
        with db_session('core') as session:
            records = (
                session.query(VocabsLearning)
                .all()
            )
            for record in records:
                cate = record.current_category
                in_process = redis.get(f"{record.in_process}")
                if not in_process and not cate:
                    # 新用户，生成单词表
                    new_cate = 1  # 从第一个category开始
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
                        default_dic = {'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}
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
                    for _ in range(add_amount):
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
                        redis.list_push(f"{record.to_review}", *list(set([x.wrong_word_id for x in words_records])), side="r")

                    # 3. 更新statis
                    default_dic = {'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}

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
                return True, logger.info("用户每日任务词表更新成功.")
            except Exception as e:
                session.rollback()
                return False, logger.info(f"用户每日任务词表更新失败：{str(e)}.")

    def generate_new_tasks(self):
        with db_session('core') as session:
            records = (
                session.query(VocabsLearning)
                .all()
            )
            s_l = []
            for record in records:
                # 1. 搜索plan,
                acc = (
                    session.query(Accounts)
                    .filter(Accounts.id == record.account_id)
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
                        if user.user_plan != 0 and user.user_plan is not None:
                            # 如果今天没有单词任务，创建
                            now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                            start_of_today = datetime(now.year, now.month, now.day)
                            tasks = (
                                session.query(TaskAccounts)
                                .filter(or_(TaskAccounts.task_id == 8, TaskAccounts.task_id == 9))
                                .filter(TaskAccounts.create_time > start_of_today)
                                .all()
                            )
                            if len(tasks) == 0:
                                # 添加任务
                                new_task = dict(
                                    account_id=record.account_id,
                                    task_id=8, #背单词
                                    is_active=1,
                                    create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                    last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                    loop=1,
                                    current_loop=1,
                                    learning_type=1,
                                )
                                new_task_ = dict(
                                    account_id=record.account_id,
                                    task_id=9, #复习单词
                                    is_active=1,
                                    create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                    last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                    loop=1,
                                    current_loop=1,
                                    learning_type=1,
                                )
                                s_l.append(new_task)
                                s_l.append(new_task_)

            if len(s_l)>0:
                session.execute(
                    insert(TaskAccounts),
                    s_l
                )

                try:
                    session.commit()
                    return True, logger.info("创建用户任务成功.")
                except Exception as e:
                    return False, logger.info(f"创建用户任务失败:{str(e)}.")
            else:
                return True, logger.info("创建用户任务成功,无需更新.")

    def run(self):
        # 1.先查看单词本与账户是否匹配 (X)
        # 2.每日的缓存数据移入主数据库, 包括（暂时保留）
        # ==> (1) 单词统计数据
        # ==> (2) 单词答题缓存数据
        # 3.每日生成新的单词本 (X)
        # 4.生成新的单词任务 (X)
        logger.info(">>>>>>>>>> 开始自动化单词服务 <<<<<<<<<")
        self.check_accounts_words_book()
        self.generate_new_words()
        self.generate_new_tasks()
        logger.info(">>>>>>>>>> 单词自动化服务结束 <<<<<<<<<")


if __name__ == "__main__":
    # 定时晚上1点执行，前期不考虑速度 -> 3与4后期可以两个线程异步进行
    VocabsService().run()
