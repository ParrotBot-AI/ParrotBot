from collections import Counter
import datetime
import statistics
from blueprints.account.models import Accounts, AccountsVocab, AccountsScores
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

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class AccountController(crudController):
    """
    account 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    """


if __name__ == '__main__':
    test = AccountController()
    create_account = {
        "user_id": 2
    }
    update_account = {
        "id": 2,
        "user_id": 3
    }

    # test._create(model=Accounts, create_params=create_account)
    test._update(model=Accounts, update_parameters=update_account, restrict_field='id')
    print(test._retrieve(model=Accounts, restrict_field='user_id', restrict_value=1))
    # test._delete(model=Accounts, restrict_field = "id", restrict_value=2)
