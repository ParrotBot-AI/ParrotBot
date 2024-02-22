from blueprints.learning.models import (
    Tasks,
    TaskAccounts,
    TaskFlows,
    Modules,
    VocabsLearning
)
from blueprints.account.models import (
    Accounts,
    AccountsVocab,
    AccountsScores,
    Users,
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
from datetime import datetime, timezone, timedelta
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class VocabLearningController(crudController):

    def fetch_vocabs(self, category_ids):
        pass

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
                    amount=50
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

    def generate_vocabs_learnings(self):
        pass

    def allocate_vocabs(self):
        with db_session('core') as session:
            records = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.current_category.is_(null()))
                .all()
            )
            accounts_need_a = [record.id for record in records]


class TaskController(crudController):

    def fetch_account_tasks(self, account_id, current_time=None, active=None):
        with db_session('core') as session:
            query = session.query(TaskAccounts).filter(TaskAccounts.account_id == account_id)
            if active is not None:
                query = query.filter(TaskAccounts.is_active == active)
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
                    session.close()
                    return s.serialize_dic(task, self.default_not_show)
            else:
                tasks = (
                    session.query(TaskFlows)
                    .filter(TaskFlows.is_active == True)
                    .filter(TaskFlows.task_id == task_id)
                    .all()
                )
                session.close()
                return s.serialize_list(tasks, self.default_not_show)


if __name__ == "__main__":
    account_id = 4
    flow = TaskController()
    # pprint(flow.fetch_account_tasks(account_id=account_id, active=True))
    # pprint(flow.fetch_module_chains(task_id=1))
    # print()
    # pprint(flow._retrieve(model=Modules, restrict_field='id', restrict_value=2))
    init = VocabLearningController()
    init.allocate_vocabs()
