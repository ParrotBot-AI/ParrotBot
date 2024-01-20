from blueprints.learning.models import (
    Stages,
    Tasks,
    TaskAccount,
    TaskFlows,
    Modules
)
from pprint import pprint
from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s
from datetime import datetime

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class TaskController(crudController):

    def fetch_account_tasks(self, account_id, current_time=None, active=None):
        with db_session('core') as session:
            query = session.query(TaskAccount).filter(TaskAccount.account_id == account_id)
            if active is not None:
                query = query.filter(TaskAccount.is_active == active)
            tasks = query.all()
            return s.serialize_list(tasks, self.default_not_show)

    def fetch_module_chains(self, task_id, module_id=None):
        # 如果不传module，将会返回整条chain
        # 如果传module，则会返回下一条
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
                    return s.serialize_dic(task, self.default_not_show)
            else:
                tasks = (
                    session.query(TaskFlows)
                    .filter(TaskFlows.is_active == True)
                    .filter(TaskFlows.task_id == task_id)
                    .all()
                )
                return s.serialize_list(tasks, self.default_not_show)


if __name__ == "__main__":
    account_id = 4
    flow = TaskController()
    # pprint(flow.fetch_account_tasks(account_id=account_id, active=True))
    print()
    # pprint(flow.fetch_module_chains(task_id=1))
    # print()
    pprint(flow._retrieve(model=Modules, restrict_field='id', restrict_value=2))
    if DATABASE_SELECTION == 'postgre':
        from configs.postgre_config import BASES
    elif DATABASE_SELECTION == 'mysql':
        from configs.mysql_config import BASES
    print(BASES['core'].metadata.tables.keys())
