from collections import Counter
from datetime import datetime, timezone, timedelta, date
import statistics
from blueprints.account.models import (
    Accounts,
    Users
)
from blueprints.education.models import (
    MenuExams
)

from configs.environment import DATABASE_SELECTION
from configs.operation import MEMBER_DAY_OFF

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
    def account_additional_info(self, account_id):
        with db_session('core') as session:
            res = {}
            record = (
                session.query(Accounts)
                .filter(Accounts.id == account_id)
                .one_or_none()
            )
            if record:
                user = (
                    session.query(Users)
                    .filter(Users.id == record.user_id)
                    .one_or_none()
                )
                if not user:
                    return False, "没有对应的user"

                res['study_day'] = user.total_study_days
                now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
                print(user.plan_due_time, user.id)
                if user.plan_due_time:
                    diff = user.plan_due_time - now
                    if diff.days < 0:
                        res['vip_due'] = None
                    else:
                        res['vip_due'] = diff.days
                else:
                    res['vip_due'] = None

                if record.next_test_time:
                    diff = record.next_test_time - now
                    if diff.days  < 0:
                        res['test_due'] = None
                    else:
                        res['test_due'] = diff.days
                else:
                    res['test_due'] = None
                res['est_score'] = record.estimate_score

                return True, res
            else:
                return False,"未找到用户"

    def update_questionary(self, account_id, param):
        if "id" not in param:
            param['id'] = account_id

        return self._update(model=Accounts, update_parameters=param, restrict_field='id')

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
                now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                end_day = now + timedelta(days=MEMBER_DAY_OFF)
                end_time = end_day.replace(hour=23, minute=59, second=59)
                user = {
                    "user_id": user_id,
                    "user_plan": 1,
                    "plan_due_time": end_time,
                }
                response = self._create(model=Users, create_params=user, restrict_field='user_id')
                # 注册账号
                if response[0]:
                    res = self.register_user_exams(user_id, exam_ids, session)
                    if not res[0]:
                        return False, res[1]

                    res = VocabLearningController().init_vocabs_learnings(user_id)
                    if not res[0]:
                        return False, res[1]

                    res, data = VocabLearningController().init_vocabs_books(user_id)
                    if not res:
                        return False, data

                    # 创建vocab task
                    # res, data = VocabLearningController().init_tasks(user_id)
                    # if not res:
                    #     return False, data
                    return True, 'OK.'
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
                        l['current_status'] = l['current_status'].name if l['current_status'] is not None else None
                        l['purpose'] = l['purpose'].name if l['purpose'] is not None else None
                        l['study_type'] = l['study_type'].name if l['study_type'] is not None else None
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
                        e['current_status'] = e['current_status'].name if e['current_status'] is not None else None
                        e['purpose'] = e['purpose'].name if e['purpose'] is not None else None
                        e['study_type'] = e['study_type'].name if e['study_type'] is not None else None
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
    user_id = 36
    # print(test.register_user(user_id, [1]))
    print(test.account_additional_info(account_id=27))
    # print(test.update_questionary(27, param={
    #     "current_status": "high_school",
    #     "purpose": "study_board",
    #     "study_type":  "studying",
    #     "next_test_time": "2024-06-10"
    # }))
    # print(test.get_user_accounts(25, 1))
    # print(test._create(model=Accounts, create_params={'user_id': 7, 'exam_id': 1}))
