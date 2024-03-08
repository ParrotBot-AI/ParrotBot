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
    AccountsVocab,
    AccountsScores,
    Users,
)
from sqlalchemy import select, func, Date, cast, and_, text, literal_column, case
from datetime import datetime, timedelta
from pprint import pprint
from configs.environment import DATABASE_SELECTION
from importlib import import_module

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath, iso_ts, get_today_midnight
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert
import json
from utils.redis_tools import RedisWrapper

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class VocabLearningController(crudController):

    def fetch_vocabs_level(self, account_id, exam_id=None):
        with db_session('core') as session:
            # 查找对应的exam
            if exam_id is None:
                account = (
                    session.query(Accounts)
                    .filter(Accounts.id == account_id)
                    .one_or_none()
                )
                if account:
                    exam_id = account.exam_id
                else:
                    return False, "账户"

            vocab_account = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )
            if not vocab_account:
                return False, "账户单词本未找到"

            current_cate = vocab_account.current_category
            if current_cate:
                redis = RedisWrapper('core_learning')
                number_to_finish = len(redis.lrange(f"{vocab_account.in_process}"))
                number_today = len(redis.lrange(f"{vocab_account.today_learn}"))

                # 查找Categorty对应条数
                raw_sql = text(f"""
                SELECT
                VocabsCategorys.id,
                VocabsCategorys.name,
                VocabsCategorys.`order`,
                S.counts
                FROM VocabsCategorys
                JOIN (
                SELECT VCR.category_id, COUNT(VCR.category_id) as counts FROM VocabCategoryRelationships VCR
                GROUP BY category_id
                ) S ON VocabsCategorys.id = S.category_id
                WHERE VocabsCategorys.exam_id = {exam_id} or VocabsCategorys.exam_id IS NULL
                ORDER BY `order`;
                """)
                results = session.execute(raw_sql).fetchall()

                # 逻辑就是总的需要背的，减去还需要背的，就是这个阶段背了的单词数
                # 无法找finished里面的，因为用户还可以跳词汇category
                total_amount = 0
                level_total = 0
                level_books = []
                for r in results:
                    if current_cate <= r.id:
                        total_amount += r.counts
                    if current_cate == r.id:
                        level_total = r.counts

                    level_books.append(dict(
                        id=r.id,
                        name=r.name,
                        order=r.order,
                        counts=r.counts
                    ))
                at_level = total_amount - (number_to_finish +number_today)

                # 响应结果
                resp = {
                    "current_level":current_cate,
                    "level_status": at_level,
                    "level_total":level_total,
                    "level_book":level_books
                }
                return True, resp
            else:
                return False, "词表未生成"




    def fetch_past_5_days_list(self, t_interval, account_id):
        with db_session('core') as session:
            date_series_sql = " ".join(
                [f"UNION ALL SELECT CURDATE() - INTERVAL {i} DAY\n" for i in range(1, t_interval)])
            raw_sql = text(f"""
            SELECT
              DateSeries.day,
              SUM(Data.wrong_word) AS w_c,
              SUM(Data.correct_word) AS c_c
            FROM (
              SELECT CURDATE() as 'day'
              {date_series_sql}
            ) DateSeries
            LEFT JOIN (
              SELECT
                DATE(time) AS day,
                wrong_word_id IS NOT NULL AS wrong_word,
                correct_word_id IS NOT NULL AS correct_word
              FROM VocabsLearningRecords
              WHERE account_id = {account_id}
                AND time >= CURDATE() - INTERVAL {t_interval - 1} DAY
            ) AS Data ON DateSeries.day = Data.day
            GROUP BY DateSeries.day
            ORDER BY DateSeries.day DESC;
            """)

            # Execute the raw SQL query
            return session.execute(raw_sql).fetchall()

    def fetch_account_vocab(self, account_id):
        redis = RedisWrapper('core_cache')
        cache_resp = redis.get(f'VocabsStatics:{account_id}')
        if cache_resp:
            return True, cache_resp

        with db_session('core') as session:
            resp = {}
            account = (
                session.query(Accounts)
                .filter(Accounts.id == account_id)
                .one_or_none()
            )
            if not account:
                return False, "未找到该账户"

            record = (
                session.query(VocabsLearning)
                .filter(VocabsLearning.account_id == account_id)
                .one_or_none()
            )

            if record:
                user = (
                    session.query(Users)
                    .filter(Users.id == account.user_id)
                    .one_or_none()
                )
                if user:
                    resp['vocab'] = user.vocab_level
                    resp['last_day_review'] = record.last_day_review
                    resp['last_day_study'] = record.last_day_study
                    resp['today_day_study'] = record.today_day_study
                    resp['today_day_review'] = record.today_day_review
                    resp['total_study'] = record.total_study
                    resp['total_review'] = record.total_review

                    # 搜索过去5天的正确的与错误的
                    results = self.fetch_past_5_days_list(t_interval=5, account_id=account_id)
                    s_l = []
                    for result in results:
                        r = dict(
                            day=result.day.strftime('%Y-%m-%d'),
                            wrong_words=int(result.w_c) if result.w_c else 0,
                            correct_words=int(result.c_c) if result.c_c else 0
                        )
                        s_l.append(r)

                    resp['series'] = s_l
                    # res, data = self.fetch_vocabs_level(account_id, account.exam_id)
                    # if res:
                    #     resp['status_book'] = data

                    # 缓存
                    redis.set(f'VocabsStatics:{account_id}', resp)

                    return True, resp
                else:
                    return False, "未找到该用户"
            else:
                return False, "未找到该账号单词"

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

    def fetch_account_tasks(self, account_id, after_time=None, active=None, type=None):
        with db_session('core') as session:
            query = session.query(TaskAccounts).filter(TaskAccounts.account_id == account_id)
            if active is not None:
                query = query.filter(TaskAccounts.is_active == active)
            if after_time is not None:
                query = query.filter(TaskAccounts.create_time > after_time)
            if type is not None:
                query = query.filter(TaskAccounts.learning_type == type)
            tasks = query.all()
            resp = []
            for task in tasks:
                tas = {}
                record = (
                    session.query(Tasks)
                    .filter(Tasks.id == task.task_id)
                    .one_or_none()
                )
                if record:
                    tas['task_account_id'] = task.id
                    tas['task_name'] = record.task_name
                    tas['order'] = record.order
                    tas['is_complete'] = task.is_complete
                    tas['complete_p'] = task.complete_percentage
                    resp.append(tas)
                else:
                    return False, "未找到相关任务"

            return True, resp

    def search_next_chain(self, response: dict, payload: dict, **kwargs):
        chain = response['chain']
        current_m = response['current_m']
        current_task = response['current_task']

        if current_task['out_function']:
            info = json.loads(current_task['out_function'])
            # out function should be a json has three attributes:
            # modules, method, payload
            module, method, payload_ = info['module'], info['method'], info['payload']
            # 运行下一步返回参数函数
            module = import_module(module)
            function = getattr(module, method)
            print(function.__name__)
            input = response.copy()
            input['payload'] = payload
            resp, data = function(**input)
            if resp:
                # to do 更新 start data
                tasks = [item for item in chain if item['from_module_id'] == current_m]
                next_task = None
                if len(tasks) > 1:
                    for task in tasks:
                        result = json.loads(task['result'])
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
        else:
            return False, "开始任务失败，任务链条件函数获取失败"

    def fetch_module_chains_conditions(self, task_account_id):
        with db_session('core') as session:
            records = (
                session.query(
                    TaskFlows.from_module_id,
                    TaskFlows.to_module_id,
                    TaskFlows.condition_id,
                    TaskFlows.result,
                    TaskFlowsConditions.in_function,
                    TaskFlowsConditions.out_function,
                    TaskFlowsConditions.condition
                )
                .join(Tasks, Tasks.id == TaskFlows.task_id)
                .join(TaskAccounts, Tasks.id == TaskAccounts.task_id)
                .join(TaskFlowsConditions, TaskFlows.condition_id == TaskFlowsConditions.id)
                .filter(TaskAccounts.id == task_account_id)
                .filter(TaskFlows.is_active == 1)
                .filter(TaskFlowsConditions.is_active == 1)
                .all()
            )
            resp = []
            for record in records:
                dic = dict(
                    from_module_id=record.from_module_id,
                    to_module_id=record.to_module_id,
                    condition_id=record.condition_id,
                    result=record.result,
                    in_function=record.in_function,
                    out_function=record.out_function,
                    condition=record.condition
                )
                resp.append(dic)
            return True, resp

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
                # 一并返回conditions
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

    def start_task(self, task_account_id):
        # 获取taskAccount (看有几个loop, current_loop)
        # 生成一个task_chain (最好是graph格式) ->缓存
        # 找到第一个module
        # 生成第一个module所需的数据， 返回

        # 运用缓存，减少读写: 2次搜索
        res = {}
        cache = {}
        with db_session('core') as session:
            record = (
                session.query(TaskAccounts)
                .filter(TaskAccounts.id == task_account_id)
                .one_or_none()
            )
            if record:
                task = (
                    session.query(Tasks)
                    .filter(Tasks.id == record.task_id)
                    .one_or_none()
                )
                res['account_id'] = record.account_id
                res['task_name'] = task.task_name
                res['task_id'] = record.task_id
                res['loop'] = record.loop
                res['current_loop'] = record.current_loop
                res['task_account_id'] = task_account_id

        current_task, pointer = None, None
        if res != {}:
            resp, data = self.fetch_module_chains_conditions(task_account_id=task_account_id)
            if resp:
                res['chain'] = data
                current_task = [item for item in data if item['from_module_id'] is None][0]
            else:
                return False, "开始任务失败，任务链获取失败"

        res['current_m'] = current_task['to_module_id']
        res['current_task'] = current_task

        try:
            if current_task['in_function']:
                info = json.loads(current_task['in_function'])
                # out function should be a json has three attributes:
                # modules, method, payload
                module, method, payload = info['module'], info['method'], info['payload']
                # 运行下一步返回参数函数
                module = import_module(module)
                function = getattr(module, method)
                resp, data, return_c = function(account_id)
                if resp:
                    # cache the chain
                    redis = RedisWrapper('core_cache')
                    redis.set(f"TaskAccount{task_account_id}", res)
                    if return_c:
                        # to do 更新 start time
                        return True, {
                            "payload": data
                        }
                else:
                    return False, data

        except Exception as e:
            return False, f"开始任务失败, 条件任务函数运行失败 {e}"

    def send_module_outcome(self, next_task, task_account_id, response):
        # 2次搜索， 2次function
        response['current_task'] = next_task
        response['current_m'] = next_task['to_module_id']
        try:
            if next_task['in_function']:
                info = json.loads(next_task['in_function'])
                # out function should be a json has three attributes:
                # modules, method, payload
                module, method, payload = info['module'], info['method'], info['payload']
                # 运行下一步返回参数函数
                module = import_module(module)
                function = getattr(module, method)
                print(function.__name__)
                resp, data, return_c = function(**response)
                if resp:
                    response['condition_id'] = next_task['condition_id']

                    if return_c:
                        redis = RedisWrapper('core_cache')
                        redis.set(f"TaskAccount{task_account_id}", response)
                        return True, {
                            "payload": data
                        }

                    else:
                        # out_function
                        if next_task['out_function']:
                            info = json.loads(next_task['out_function'])
                            module, method, payload = info['module'], info['method'], info['payload']
                            # 运行下一步返回参数函数
                            module = import_module(module)
                            function = getattr(module, method)

                            resp, data = function(**response)
                            if resp:
                                response['condition_id'] = next_task['condition_id']

                                # redo the loop
                                if data == "redo":
                                    return self.start_task(task_account_id)

                                # finished the loop
                                elif data == "finished":

                                    return True, data
                                else:
                                    return True, data
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

    def rec_module_outcome(
            self,
            task_account_id,
            payload,
            **kwargs):

        redis = RedisWrapper('core_cache')
        task_flow = redis.get(f"TaskAccount{task_account_id}")
        if task_flow:
            resp, next_task = self.search_next_chain(response=task_flow, payload=payload['payload'])
            if resp:
                return self.send_module_outcome(next_task, task_account_id, task_flow)
            else:
                return False, next_task
        else:
            return False, '找不到任务信息'


if __name__ == "__main__":
    account_id = 20
    # flow = TaskController()
    # pprint(flow.fetch_account_tasks(account_id=account_id, after_time=get_today_midnight(), active=True))
    flow = VocabLearningController()
    pprint(flow.fetch_vocabs_level(account_id=account_id))
    # Get the time at 00:00 AM on today's date
    # resp, payload = flow.start_task(task_account_id=2)
    # payload = {'payload': {'endpoint': 'gpt-endpint', 'method': 'sse', 'api_key': 'key', 'execute': True, 'target': ['execute']}}
    # payload = {'payload': {'answer': [0, 0, 0, 0],
    #                 'correct_answer': [1, 0, 0, 0],
    #                 'stem': ['n. 工程；课题、作业', 'n. 建筑', 'n. 发展；生长；开发', 'n. 主动权，自主权'],
    #                 'target': ['answer'],
    #                 'word': 'project',
    #                 'word_id': 34001,
    #                 'word_ids': [34001, 35082, 35964, 34573]}}
    # print(flow.rec_module_outcome(task_account_id=2, payload=payload))
    # pprint(flow.fetch_module_chains_conditions(task_account_id=2)[1])
    # dic = {'condition_id': 3,
    #         'current_loop': 1,
    #         'current_m': 6,
    #         'loop': 1,
    #         'payload': {'answer': [1, 0, 0, 0],
    #                 'correct_answer': [1, 0, 0, 0],
    #                 'stem': ['n. 工程；课题、作业', 'n. 建筑', 'n. 发展；生长；开发', 'n. 主动权，自主权'],
    #                 'target': ['answer'],
    #                 'word': 'project',
    #                 'word_id': 34001,
    #                 'word_ids': [34001, 35082, 35964, 34573]}
    #         'task_account_id': 2,
    #         'task_flow_id': 7,
    #         'task_id': 8,
    #         'task_name': '学习新单词',
    #         'account_id': 4
    #        }
    # dic = {'condition_id': 2,
    #         'current_loop': 1,
    #         'current_m': 7,
    #         'loop': 1,
    #         'payload': {
    #               'api_key': 'key',
    #             'endpoint': 'gpt-endpint',
    #             'execute': False,
    #             'method': 'sse',
    #             'target': ['execute']},
    #         'task_account_id': 2,
    #         'task_flow_id': 5,
    #         'task_id': 8,
    #         'task_name': '学习新单词',
    #         'account_id':4
    #        }
    # pprint(flow.rec_module_outcome(response=dic))
    # print()
    # pprint(flow._retrieve(model=Modules, restrict_field='id', restrict_value=2))
    # init = VocabLearningController()
    # init.allocate_vocabs()
