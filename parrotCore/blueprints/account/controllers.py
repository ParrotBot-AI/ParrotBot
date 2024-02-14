from collections import Counter
import datetime
import statistics
from blueprints.account.models import (
    Accounts,
    AccountsVocab,
    AccountsScores,
    Users
)
from blueprints.education.models import (
    MenuExams
)
from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session
from pprint import pprint
import simplejson as json
from utils import abspath
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class AccountController(crudController):
    """
    account 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    """

    def register_user(self, user_id, exam_ids):
        user = {"user_id": user_id}
        response = self._create(model=Users, create_params=user, restrict_field='user_id')
        # 注册账号
        if response[0]:
            user = self._retrieve(model=Users, restrict_field='user_id', restrict_value=user_id)
            index_id = s.serialize_dic(user, self.default_not_show)['id']
            print(index_id)
            with db_session('core') as session:
                for each in exam_ids:
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    merged_dict = {**default_dic, **{'user_id': index_id, 'exam_id': each}}
                    record = Accounts(**merged_dict)
                    session.add(record)

                try:
                    session.commit()
                    return True, ""
                except Exception as e:
                    session.rollback()
                    return False, str(e)
        else:
            return False, 'False to register, already exists'

    def get_menu_exams(self, menu_ids):
        with db_session('core') as session:
            records = (
                session.query(MenuExams)
                .filter(MenuExams.menu_id.in_(menu_ids))
                .all()
            )
            return True, s.serialize_list(records)




if __name__ == '__main__':
    test = AccountController()
    user_id = 1
    print(test.register_user(38, [1]))
    # print(test._create(model=Accounts, create_params={'user_id': 7, 'exam_id': 1}))
