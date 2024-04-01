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
from configs.environment import DATABASE_SELECTION
from sqlalchemy.sql.expression import bindparam

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath
from utils.logger_tools import get_general_logger
from datetime import datetime, timezone, timedelta
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert
from utils.redis_tools import RedisWrapper
from configs.operation import JUMP_NEED_PERCENTAGE, JUMP_NEED_STUDY_AMOUNT

logger = get_general_logger('vocab_log', path=abspath('logs', 'vocab_service'))


class TasksService:
    # 每日定时任务，单词本管理
    # 单词本保持 !!!右进左出!!!!!

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
                if not cate:
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
                            .filter(or_(VocabCategorys.exam_id == exam, VocabCategorys.exam_id is None))
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
                        .filter(VocabsLearningRecords.account_id == record.account_id)
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
                return True, logger.info("用户每日任务词表更新成功.")
            except Exception as e:
                session.rollback()
                return False, logger.info(f"用户每日任务词表更新失败：{str(e)}.")

    def deal_weekly_tasks(self):
        today_date = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        is_monday = today_date.weekday() == 0
        start_of_today = datetime(today_date.year, today_date.month, today_date.day)

        if not is_monday:
            return True, logger.info("未到生成周度任务时间（不是周一凌晨）")

        s_l = []
        with db_session('core') as session:
            account_records = (
                session.query(Accounts.id, Users.user_plan)
                .join(Users, Accounts.user_id == Users.id)
                .all()
            )
            for record in account_records:
                if record.user_plan != 0 and record.user_plan is not None:
                    tasks = (
                        session.query(TaskAccounts)
                        .filter(TaskAccounts.task_id == 10)
                        .filter(TaskAccounts.account_id == record.id)
                        .filter(TaskAccounts.create_time > start_of_today)
                        .all()
                    )
                    if len(tasks) == 0:
                        # calculate new sunday nighttime:
                        days_to_add = 6 - today_date.weekday() if today_date.weekday() < 6 else 0
                        next_sunday = today_date + timedelta(days=days_to_add)
                        next_sunday_end = next_sunday.replace(hour=23, minute=59, second=59, microsecond=0)
                        new_task = dict(
                            account_id=record.id,
                            task_id=10,  # 模考
                            is_active=1,
                            create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            last_update_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                            loop=1,
                            current_loop=0,
                            level=1,  # 周度任务
                            due_time=next_sunday_end,
                            learning_type=2,
                        )
                        s_l.append(new_task)

            if len(s_l) > 0:
                session.execute(
                    insert(TaskAccounts),
                    s_l
                )
                try:
                    session.commit()
                    return True, logger.info("创建用户周度任务成功.")
                except Exception as e:
                    return False, logger.info(f"创建用户周度任务失败:{str(e)}.")
            else:
                return True, logger.info("创建用户周度任务成功,无需更新.")

    def generate_new_vocab_tasks(self):
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
                                .filter(TaskAccounts.account_id == record.account_id)
                                .filter(TaskAccounts.create_time > start_of_today)
                                .all()
                            )
                            if len(tasks) == 0:
                                # 添加任务
                                from configs.operation import STUDY_LOOP
                                new_task = dict(
                                    account_id=record.account_id,
                                    task_id=8,  # 背单词
                                    is_active=1,
                                    create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                    last_update_time=datetime.now(timezone.utc).astimezone(
                                        timezone(timedelta(hours=8))),
                                    loop=STUDY_LOOP,
                                    current_loop=0,
                                    level=0,
                                    due_time=datetime.now(timezone.utc).astimezone(
                                        timezone(timedelta(hours=8))).replace(hour=23, minute=59, second=59),
                                    learning_type=1,
                                )
                                new_task_ = dict(
                                    account_id=record.account_id,
                                    task_id=9,  # 复习单词
                                    is_active=1,
                                    create_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                                    last_update_time=datetime.now(timezone.utc).astimezone(
                                        timezone(timedelta(hours=8))),
                                    loop=1,
                                    current_loop=0,
                                    level=0,
                                    due_time=datetime.now(timezone.utc).astimezone(
                                        timezone(timedelta(hours=8))).replace(hour=23, minute=59, second=59),
                                    learning_type=1,
                                )
                                s_l.append(new_task)
                                s_l.append(new_task_)

            if len(s_l) > 0:
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

    def check_whether_jump(self):
        with db_session('core') as session:
            records = (
                session.query(VocabsLearning)
                .all()
            )
            u_r = []
            for record in records:
                account_id = record.account_id
                cate = record.current_category
                is_skip_triggered = record.is_skip_remind
                is_refused = record.refuse_skip

                vocabs_records = (
                    session.query(
                        VocabsLearningRecords.study_word_id,
                        VocabsLearningRecords.wrong_word_id,
                        VocabsLearningRecords.correct_word_id,
                        VocabsLearning.current_category
                    )
                    .join(VocabCategoryRelationships,
                          (VocabCategoryRelationships.word_id == VocabsLearningRecords.correct_word_id) |
                          (VocabCategoryRelationships.word_id == VocabsLearningRecords.wrong_word_id))
                    .join(VocabsLearning, VocabsLearningRecords.account_id == VocabsLearning.account_id)
                    .join(VocabCategorys, VocabsLearning.current_category == VocabCategorys.id)
                    .filter(VocabsLearningRecords.account_id == account_id)
                    .all()
                )
                total_current_study = sum([1 for x in vocabs_records if x.study_word_id is not None])
                correct_number = len(
                    list(set([x.correct_word_id for x in vocabs_records if x.correct_word_id is not None])))
                wrong_number = len(list(set([x.wrong_word_id for x in vocabs_records if x.wrong_word_id is not None])))
                if total_current_study > JUMP_NEED_STUDY_AMOUNT:
                    if correct_number / (correct_number + wrong_number) * 100 > JUMP_NEED_PERCENTAGE:

                        # 如果之前已经拒绝升级，不再提醒升级
                        if not (is_skip_triggered is not None and is_refused is None):
                            update_u = {
                                "u_id": account_id,
                                "is_skip_remind": 1,
                                "refuse_skip": False
                            }
                            logger.info(f"账户{account_id}满足升级条件.")
                            u_r.append(update_u)

            if len(u_r) == 0:
                return True, logger.info("无需用户需要词汇升级，成功.")

            session.execute(
                update(VocabsLearning).where(VocabsLearning.id == bindparam('u_id')).values(
                    is_skip_remind=bindparam('is_skip_remind'),
                    refuse_skip=bindparam('refuse_skip'),
                ),
                u_r
            )
            try:
                session.commit()
                return True, logger.info("用户词汇升级检查成功.")
            except Exception as e:
                return False, logger.info("用户词汇升级检查失败.")

    def run(self):
        # 1.先查看单词本与账户是否匹配 (X)
        # 2.每日的缓存数据移入主数据库, 包括（暂时保留）
        # ==> (1) 单词统计数据
        # ==> (2) 单词答题缓存数据
        # 3.每日生成新的单词本 (X)
        # 4.生成新的单词任务 (X)
        # 5.检测用户是否需要跳级词汇， 目前满足条件 (该阶段学满35个 & 该阶段有90%的正确率)
        # 6.生成周度任务
        logger.info(">>>>>>>>>> 开始自动化用户任务服务 <<<<<<<<<")
        self.check_accounts_words_book()
        self.generate_new_words()
        self.generate_new_vocab_tasks()
        self.check_whether_jump()
        self.deal_weekly_tasks()
        logger.info(">>>>>>>>>> 单词自动化用户任务服务结束 <<<<<<<<<")


if __name__ == "__main__":
    # 定时晚上12:01点执行，前期不考虑速度 -> 后期可以多线程异步进行
    TasksService().run()
