from blueprints.learning.models import (
    TaskAccounts,
    StudyPulseRecords
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
import json
from utils.redis_tools import RedisWrapper

logger = get_general_logger('daily_log', path=abspath('logs', 'daily_service'))


class DailyService:
    # 每日定时任务，每日事务处理

    def clean_model_usage(self):
        from blueprints.account.models import Accounts
        with db_session('core') as session:
            records = (
                session.query(Accounts)
                .all()
            )
            s_l = []
            for account in records:
                if account.model_today_used > 0:
                    r = {
                        "a_id": account.id,
                        "model_today_used":0
                    }
                    s_l.append(r)

            if len(s_l) == 0:
                return True, logger.info("清除用户的当日的model_usage记录，成功.")

            session.execute(
                update(Accounts).where(Accounts.id == bindparam('a_id')).values(
                    model_today_used=bindparam('model_today_used'),
                ),
                s_l
            )

            try:
                session.commit()
                return True, logger.info("清除用户的当日的model_usage记录成功.")
            except Exception as e:
                return False, logger.info(f"清除用户的当日的model_usage记录失败.")

    def users_tasks(self):
        from blueprints.account.models import Users, Accounts

        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        yes = now - timedelta(days=1)
        start_of_today = datetime(yes.year, yes.month, yes.day)
        with db_session('core') as session:
            records = (
                session.query(Users)
                .all()
            )

            u_r = []
            for user in records:
                task_complete, study = 0, 0
                accounts_records = (
                    session.query(Accounts)
                    .filter(Accounts.user_id == user.id)
                    .all()
                )
                accounts = [x.id for x in accounts_records]
                for account_id in accounts:
                    tasks_accounts = (
                        session.query(TaskAccounts)
                        .filter(TaskAccounts.account_id == account_id)
                        .filter(TaskAccounts.create_time >= start_of_today)
                        .all()
                    )
                    task_complete += sum([1 for x in tasks_accounts if x.is_complete == 1])

                    study_records = (
                        session.query(StudyPulseRecords)
                        .filter(StudyPulseRecords.account_id == account_id)
                        .filter(StudyPulseRecords.create_time >= start_of_today)
                        .all()
                    )
                    if (len(study_records)) > 1:
                        study = 1

                update_u = {
                    "u_id":user.id,
                    "task_complete": user.task_complete + task_complete,
                    "total_study_days": user.total_study_days if user.total_study_days is not None else 0 + study
                }
                u_r.append(update_u)

            if len(u_r) == 0:
                return True, logger.info("无需更新用户事务记录，成功.")

            session.execute(
                update(Users).where(Users.id == bindparam('u_id')).values(
                    task_complete=bindparam('task_complete'),
                    total_study_days=bindparam('total_study_days'),
                ),
                u_r
            )

            try:
                session.commit()
                return True, logger.info("更新用户事务记录成功.")
            except Exception as e:
                return False, logger.info(f"更新用户事务记录失败.")

    def clean_old_tasks(self):
        redis = RedisWrapper("core_cache")
        keys = redis.keys()
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        start_of_today = datetime(now.year, now.month, now.day)

        with db_session('core') as session:
            for key in keys:
                if "TaskAccount:" in key:
                    tasks_account = (
                        session.query(TaskAccounts)
                        .filter(TaskAccounts.id == int(key.split(":")[1]))
                        .one_or_none()
                    )
                    if tasks_account:
                        if tasks_account.create_time < start_of_today:
                            redis.delete(key)

            return True, logger.info("移除过期任务记录成功.")

    def clean_old_sheets(self):
        # 避免冲突，保存两天前过期的试卷
        from blueprints.education.models import AnswerSheetRecord
        from blueprints.education.controllers import AnsweringScoringController
        redis = RedisWrapper("core_cache")
        keys = redis.keys()
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        yes = now - timedelta(days=1)
        start_of_day = datetime(yes.year, yes.month, yes.day)

        with db_session('core') as session:
            for key in keys:
                if "Sheet-" in key:
                    sheet_id = key.split("-")[1]

                    # 考虑到后期转换为uuid
                    if sheet_id.isdigit():
                        sheet_id = int(sheet_id)

                    sheet = (
                        session.query(AnswerSheetRecord)
                        .filter(AnswerSheetRecord.id == sheet_id)
                        .one_or_none()
                    )
                    if sheet:
                        if sheet.end_time < start_of_day and sheet.status == 1:
                            try:
                                res, data = AnsweringScoringController().save_answer(sheet_id=sheet_id)
                                logger.info(f"移除过期试卷{sheet_id}记录成功.")
                                if res:
                                    redis.delete(key)
                                else:
                                    logger.info(f"移除过期试卷{sheet_id}记录失败 {str(data)}.")
                            except Exception as e:
                                logger.info(f"移除过期试卷{sheet_id}记录失败 {str(e)}.")

            return True, logger.info("移除过期试卷记录成功.")


    def run(self):
        # 1.清除用户的当日的model_use记录，设置为0
        # 2.更新用户total study day和task_complete记录
        # 3.清除过期的缓存里过期的task
        # 4.保存，清除过期的试卷
        logger.info(">>>>>>>>>> 开始每日事务服务 <<<<<<<<<")
        # self.clean_model_usage()
        # self.users_tasks()
        # self.clean_old_tasks()
        self.clean_old_sheets()
        logger.info(">>>>>>>>>> 每日事务服自动化服务结束 <<<<<<<<<")


if __name__ == "__main__":
    # 定时晚上01:01点执行 (与单词任务不冲突)，前期不考虑速度 -> 后期可以多个线程异步进行
    DailyService().run()
