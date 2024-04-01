from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session
from utils.redis_tools import RedisWrapper
from utils import iso_ts
from datetime import datetime, timedelta, timezone
import pprint
# =====================================In Function (3 outputs)=================================#
def fetch_mock_resource(
        account_id=None,
        exam_id=1,
        **kwargs
):
    from blueprints.education.controllers import TransactionsController
    import random
    try:

        res, resources = TransactionsController()._get_all_resources_under_exams(exam_id, account_id)
        if not res:
            return False, f"无法获取resources", False

        all_resources = []
        for each in resources:
            all_resources += each['children']

        # all_resources = [x['children'] for x in resources][:]
        a_resources = [x for x in all_resources if x['score'] is None]
        if len(a_resources) > 0:
            choose = random.choice(a_resources)
        else:
            choose = random.choice(all_resources)

        response = {
            "finished": False,
            "target": ['finished'],
            "task": choose
        }
        return True, response, True
    except Exception as e:
        return False, f"{str(e)}", False


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


# =====================================OUT Function (2 outputs)=================================#
def fetch_mock_execute(
        payload,
        account_id,
        **kwargs
):
    try:
        if payload['finished']:
            return True, {}
        return False, ""
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



