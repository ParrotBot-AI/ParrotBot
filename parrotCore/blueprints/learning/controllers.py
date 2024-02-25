from blueprints.learning.models import (
    Tasks,
    TaskAccounts,
    TaskFlows,
    Modules,
    VocabsLearning,
    TaskFlowsConditions
)
from blueprints.account.models import (
    Accounts,
    AccountsVocab,
    AccountsScores,
    Users,
)
from pprint import pprint
from configs.environment import DATABASE_SELECTION
from blueprints.learning import vocab_learning
from importlib import import_module

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath, iso_ts, get_today_midnight
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s
from datetime import datetime, timezone, timedelta
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert
import json
from utils.redis_tools import RedisWrapper

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
                    today_learn=f'{account_id}:today',
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

    def fetch_account_tasks(self, account_id, after_time=None, active=None):
        with db_session('core') as session:
            query = session.query(TaskAccounts).filter(TaskAccounts.account_id == account_id)
            if active is not None:
                query = query.filter(TaskAccounts.is_active == active)
            if after_time is not None:
                query = query.filter(TaskAccounts.create_time > after_time)
            tasks = query.all()
            return True, s.serialize_list(tasks, self.default_not_show)

    def search_next_chain(self, response:dict, **kwargs):
        task_id, module_id, payload, condition_id = response['task_id'], response['current_m'],response['payload'], response['condition_id']
        # 搜索 2次，执行2个function
        with db_session('core') as session:
            tasks = (
                session.query(TaskFlows)
                .filter(TaskFlows.is_active == True)
                .filter(TaskFlows.from_module_id == module_id)
                .all()
            )

            record = (
                session.query(TaskFlowsConditions)
                .filter(TaskFlowsConditions.id == condition_id)
                .one_or_none()
            )
            if record:
                try:
                    if record.out_function:
                        info = json.loads(record.out_function)
                        # out function should be a json has three attributes:
                        # modules, method, payload
                        module, method, payload_ = info['module'], info['method'], info['payload']
                        # 运行下一步返回参数函数
                        module = import_module(module)
                        function = getattr(module, method)
                        print(function.__name__)
                        resp, data = function(**response)
                        if resp:
                            # to do 更新 start data
                            next_task = None
                            if len(tasks) > 1:
                                for task in tasks:
                                    result = json.loads(task.result)
                                    type, value, re = result['type'], result['value'], result['r']
                                    # type_function = globals()[type]
                                    expression = f"{data} {re} {value}"
                                    if eval(expression):
                                        next_task = task
                                        break
                                return True, next_task
                            else:
                                return True, tasks[0]
                        else:
                            return False, data
                except Exception as e:
                    return False, f"开始任务失败, 条件任务函数运行失败 {e}"

            else:
                return False, "开始任务失败，任务链条件函数获取失败"

    def fetch_module_chains(self, account_id, task_id, module_id=None):
        # 如果不传module，将会返回整条chain
        # 如果传module，则会返回下一条
        # 2次搜索
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
                    return True, s.serialize_dic(task, self.default_not_show)
            else:
                tasks = (
                    session.query(TaskFlows)
                    .filter(TaskFlows.is_active == True)
                    .filter(TaskFlows.task_id == task_id)
                    .all()
                )
                if tasks:
                    for task in tasks:
                        if task.from_module_id is None:
                            first_module = task.to_module_id
                            id = task.id

                    r = {}
                    l = s.serialize_list(tasks, self.default_not_show)
                    for item_ in l:
                        r[item_['id']] = item_

                    response = {
                        "current_m": first_module,
                        "task_flow_id": id,
                        "chain": r
                    }

                    # session.close()
                    return True, response
                else:
                    return False, "未找到任务链"

    def start_task(self, account_id, taskAccount_id):
        # 获取taskAccount (看有几个loop, current_loop)
        # 生成一个task_chain (最好是graph格式) ->缓存
        # 找到第一个module
        # 生成第一个module所需的数据， 返回

        # TO DO： # 4次搜索， function最坏3次搜索 （最坏7次）
        # 运用缓存，减少读写
        res = {}
        cache = {}
        with db_session('core') as session:
            record = (
                session.query(TaskAccounts)
                .filter(TaskAccounts.id == taskAccount_id)
                .one_or_none()
            )
            if record:
                task = (
                    session.query(Tasks)
                    .filter(Tasks.id == record.task_id)
                    .one_or_none()
                )
                res['task_name'] = task.task_name
                res['task_id'] = record.task_id
                res['loop'] = record.loop
                res['current_loop'] = record.current_loop
                res['task_account_id'] = taskAccount_id

                cache = s.serialize_dic(record, self.default_not_show)
                redis = RedisWrapper('core_cache')

        if res != {}:
            resp = self.fetch_module_chains(self, task_id=record.task_id)
            if resp[0]:
                res.update(**resp[1])
            else:
                return False, "开始任务失败，任务链获取失败"

        # 找到第一个module，执行相关信息
        start_condition_id = res['chain'][res['task_flow_id']]['condition_id']
        if start_condition_id:
            record = (
                session.query(TaskFlowsConditions)
                .filter(TaskFlowsConditions.id == start_condition_id)
                .one_or_none()
            )
            if record:
                try:
                    if record.in_function:
                        info = json.loads(record.in_function)
                        # out function should be a json has three attributes:
                        # modules, method, payload
                        module, method, payload = info['module'], info['method'], info['payload']
                        # 运行下一步返回参数函数
                        module = import_module(module)
                        function = getattr(module, method)
                        resp, data, return_c = function(account_id)
                        if resp:
                            del res['chain']
                            res['condition_id'] = start_condition_id
                            res['payload'] = data
                            if return_c:
                                # to do 更新 start time
                                return True, res
                        else:
                            return False, data

                except Exception as e:
                    return False, f"开始任务失败, 条件任务函数运行失败 {e}"
        else:
            return False, "开始任务失败，任务链条件函数获取失败"

    def send_module_outcome(self, taskFlow, response):
        # 2次搜索， 2次function
        res = {}
        loop, current_loop, task_account_id = response['loop'], response['current_loop'], response['task_account_id']
        with db_session('core') as session:
            task = (
                session.query(Tasks)
                .filter(Tasks.id == taskFlow.task_id)
                .one_or_none()
            )
            res['task_name'] = task.task_name
            res['task_id'] = taskFlow.task_id
            res['loop'] = loop
            res['current_loop'] = current_loop
            res['task_flow_id'] = taskFlow.id
            res['current_m'] = taskFlow.to_module_id
            res['task_account_id'] = task_account_id

            # 找到第一个module，执行相关信息
        condition_id = taskFlow.condition_id
        if condition_id:
            record = (
                session.query(TaskFlowsConditions)
                .filter(TaskFlowsConditions.id == condition_id)
                .one_or_none()
            )
            if record:
                try:
                    if record.in_function:
                        info = json.loads(record.in_function)
                        # out function should be a json has three attributes:
                        # modules, method, payload
                        module, method, payload = info['module'], info['method'], info['payload']
                        # 运行下一步返回参数函数
                        module = import_module(module)
                        function = getattr(module, method)
                        print(function.__name__)
                        resp, data, return_c = function(**res)
                        if resp:
                            res['condition_id'] = condition_id
                            res['payload'] = data

                            if return_c:
                                return True, res

                            else:
                                # out_function
                                if record.out_function:
                                    info = json.loads(record.out_function)
                                    # out function should be a json has three attributes:
                                    # modules, method, payload
                                    module, method, payload = info['module'], info['method'], info['payload']
                                    # 运行下一步返回参数函数
                                    module = import_module(module)
                                    function = getattr(module, method)

                                    resp, data = function(**res)
                                    if resp:
                                        res['condition_id'] = condition_id
                                        res['payload'] = data

                                        # redo the loop
                                        if data == "redo":
                                            return self.start_task(account_id, task_account_id)

                                        # finished the loop
                                        elif data == "finished":
                                            return True, data
                                        else:
                                            return True, res
                                    else:
                                        return False, data

                                else:
                                    return False, f"开始任务失败, 条件任务无法找到"

                        else:
                            return False, data

                    else:
                        return False, f"开始任务失败, 条件任务无法找到"
                except Exception as e:
                    return False, f"开始任务失败, 条件任务函数运行失败 {e}"
        else:
            return False, "开始任务失败，任务链条件函数获取失败"

    def rec_module_outcome(
            self,
            response,
            **kwargs):
        # 最坏10次搜索
        resp = self.search_next_chain(response=response)
        if resp[0]:
            return self.send_module_outcome(resp[1], response)
        else:
            return False, resp[1]


if __name__ == "__main__":
    account_id = 4
    flow = TaskController()
    # pprint(flow.fetch_account_tasks(account_id=account_id, after_time=get_today_midnight(), active=True))

    # pprint(flow.start_task(account_id=4, taskAccount_id=2))
    dic = {'condition_id': 3,
            'current_loop': 1,
            'current_m': 6,
            'loop': 1,
            'payload': {'answer': [1, 0, 0, 0],
                    'correct_answer': [1, 0, 0, 0],
                    'stem': ['n. 工程；课题、作业', 'n. 建筑', 'n. 发展；生长；开发', 'n. 主动权，自主权'],
                    'target': ['answer'],
                    'word': 'project',
                    'word_id': 34001,
                    'word_ids': [34001, 35082, 35964, 34573]},
            'task_account_id': 2,
            'task_flow_id': 7,
            'task_id': 8,
            'task_name': '学习新单词',
            'account_id':4
           }
    # dic = {'condition_id': 2,
    #         'current_loop': 1,
    #         'current_m': 7,
    #         'loop': 1,
    #         'payload': {'api_key': 'key',
    #             'endpoint': 'gpt-endpint',
    #             'execute': True,
    #             'method': 'sse',
    #             'target': ['execute']},
    #         'task_account_id': 2,
    #         'task_flow_id': 5,
    #         'task_id': 8,
    #         'task_name': '学习新单词',
    #         'account_id':4
    #        }
    pprint(flow.rec_module_outcome(response=dic))
    # print()
    # pprint(flow._retrieve(model=Modules, restrict_field='id', restrict_value=2))
    # init = VocabLearningController()
    # init.allocate_vocabs()
