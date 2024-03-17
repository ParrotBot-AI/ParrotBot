from collections import Counter
from datetime import datetime, timezone, timedelta, date
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
    def register_user_exams(self, user_id, exam_ids, session):
        user = self._retrieve(model=Users, restrict_field='user_id', restrict_value=user_id)
        index_id = s.serialize_dic(user, self.default_not_show)['id']

        for each in exam_ids:
            default_dic = {
                'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            }
            merged_dict = {**default_dic, **{'user_id': index_id, 'exam_id': each}}
            record = Accounts(**merged_dict)
            session.add(record)

        try:
            session.commit()
            # session.close()
            return True, "OK."
        except Exception as e:
            session.rollback()
            # session.close()
            return False, str(e)

    def register_user(self, user_id, exam_ids):
        from blueprints.learning.controllers import VocabLearningController
        with db_session('core') as session:
            record = (
                session.query(Users)
                .filter(Users.user_id == user_id)
                .one_or_none()
            )
            if record:
                return self.register_user_exams(user_id, exam_ids, session)
            else:
                user = {"user_id": user_id}
                response = self._create(model=Users, create_params=user, restrict_field='user_id')
                # 注册账号
                if response[0]:
                    res = self.register_user_exams(user_id, exam_ids, session)
                    if res[0]:
                        res = VocabLearningController().init_vocabs_learnings(user_id)
                        if res[0]:
                            res, data = VocabLearningController().init_vocabs_books(user_id)
                            if res:
                                return True, 'OK.'
                            else:
                                return False, data
                        else:
                            return False, res[1]
                else:
                    return False, response[1]

    def get_menu_exams(self, menu_ids):
        with db_session('core') as session:
            records = (
                session.query(MenuExams)
                .filter(MenuExams.menu_id.in_(menu_ids))
                .all()
            )
            session.close()
            return True, s.serialize_list(records)

    def get_user_accounts(self, user_id, exam_id=None):
        with db_session('core') as session:
            record = (
                session.query(Users)
                .filter(Users.user_id == user_id)
                .one_or_none()
            )
            if record:
                user_index = record.id
                if exam_id:
                    record = (
                        session.query(Accounts)
                        .filter(Accounts.user_id == user_index)
                        .filter(Accounts.exam_id == exam_id)
                        .one_or_none()
                    )
                    if record:
                        l = s.serialize_dic(record, self.default_not_show + ['user_id', 'last_request_time'])
                        l['account_id'] = l['id']
                        del l['id']
                        return True, l
                else:
                    records = (
                        session.query(Accounts)
                        .filter(Accounts.user_id == user_index)
                        .all()
                    )
                    l = s.serialize_list(records, self.default_not_show + ['user_id', 'last_request_time'])
                    for e in l:
                        e['account_id'] = e['id']
                        del e['id']
                    return True, l

    def get_user_info(self, user_id):
        with db_session('core') as session:
            record = (
                session.query(Users)
                .filter(Users.user_id == user_id)
                .one_or_none()
            )
            if record:
                return True, s.serialize_dic(record, self.default_not_show)
            else:
                return False, '用户未找到'




if __name__ == '__main__':
    test = AccountController()
    user_id = 6
    print(test.register_user(user_id, [1]))
    # print(test.get_user_accounts(40))
    # print(test._create(model=Accounts, create_params={'user_id': 7, 'exam_id': 1}))
