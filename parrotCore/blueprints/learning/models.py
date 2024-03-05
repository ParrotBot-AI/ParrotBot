from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Float, Text
from configs.environment import DATABASE_SELECTION

# from blueprints.education.models import (VocabBase, VocabCategorys)
from blueprints.account.models import Accounts

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import BASES
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import BASES


class Stages(BASES['core']):
    __tablename__ = "Stages"

    id = Column(Integer, autoincrement=True, primary_key=True)
    stage_name = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.stage_name})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.stage_name})'
        return s


class Tasks(BASES['core']):
    __tablename__ = "Tasks"

    id = Column(Integer, autoincrement=True, primary_key=True)
    task_name = Column(String(20), nullable=False)
    stage_id = Column(Integer, ForeignKey('Stages.id', ondelete='CASCADE'), nullable=True)
    order = Column(Integer)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.task_name})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.task_name})'
        return s


class Modules(BASES['core']):
    __tablename__ = "Modules"

    id = Column(Integer, autoincrement=True, primary_key=True)
    module_name = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.module_name})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.module_name})'
        return s

class TaskFlowsConditions(BASES['core']):
    __tablename__ = "TaskFlowsConditions"

    id = Column(Integer, autoincrement=True, primary_key=True)
    in_function = Column(Text, nullable=False)
    out_function = Column(Text, nullable=False)
    # current_module_id = Column(Integer, ForeignKey('Modules.id', ondelete='CASCADE'), nullable=False)
    condition = Column(String(30), nullable=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} in: {self.in_function} out: {self.out_function})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} in: {self.in_function} out: {self.out_function})'
        return s


class TaskFlows(BASES['core']):
    __tablename__ = "TaskFlows"

    id = Column(Integer, autoincrement=True, primary_key=True)
    task_id = Column(Integer, ForeignKey('Tasks.id', ondelete='CASCADE'), nullable=False)
    # account_id = Column(Integer, ForeignKey('Accounts.id', ondelete='CASCADE'), nullable=True)
    condition_id = Column(Integer)
    from_module_id = Column(Integer, ForeignKey('Modules.id', ondelete='CASCADE'), nullable=True)
    to_module_id = Column(Integer, ForeignKey('Modules.id', ondelete='CASCADE'), nullable=True)
    result = Column(Text)
    is_optional = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} f: {self.from_module_id} t: {self.to_module_id})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} f: {self.from_module_id} t: {self.to_module_id})'
        return s

class LearningTypes(BASES['core']):
    __tablename__ = "LearningTypes"

    id = Column(Integer, autoincrement=True, primary_key=True)
    type_name = Column(String(20))

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.type_name}'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.type_name}'
        return s


class TaskAccounts(BASES['core']):
    __tablename__ = "TaskAccounts"

    id = Column(Integer, autoincrement=True, primary_key=True)
    account_id = Column(Integer, nullable=False)
    task_id = Column(Integer, ForeignKey('Tasks.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    is_complete = Column(Boolean, default=False)
    complete_percentage = Column(Float, default=0)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    loop = Column(Integer, default=1)
    current_loop = Column(Integer, default=1)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)
    learning_type = Column(Integer, nullable=True)

    def __str__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id} t: {self.task_id})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id} t: {self.task_id})'
        return s


class VocabsLearning(BASES['core']):
    __tablename__ = "VocabsLearning"

    id = Column(Integer, autoincrement=True, primary_key=True)
    account_id = Column(Integer, nullable=False)
    in_process = Column(String(20), nullable=False)  # key to redis
    finished = Column(String(20), nullable=False)  # key to redis
    to_review = Column(String(20), nullable=False)  # key to redis
    today_learn = Column(String(20), nullable=False) # key to redis
    unknown = Column(String(20), nullable=False)  # key to redis
    amount = Column(Integer, nullable=False)  # key to redis

    # statistics
    current_category = Column(Integer, ForeignKey('VocabsCategorys.id', ondelete='CASCADE'), nullable=True)
    last_day_review = Column(Integer, default=0)
    last_day_study = Column(Integer, default=0)
    today_day_study = Column(Integer, default=0)
    today_day_review = Column(Integer, default=0)
    total_study = Column(Integer, default=0)
    total_review = Column(Integer, default=0)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id}'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id}'
        return s

class VocabsLearningRecords(BASES['core']):
    __tablename__ = "VocabsLearningRecords"

    id = Column(Integer, autoincrement=True, primary_key=True)
    accounts_id = Column(Integer, ForeignKey('Accounts.id', ondelete='CASCADE'), nullable=False)
    reviewed_word_id = Column(Integer, ForeignKey('Vocabs.id', ondelete='CASCADE'), nullable=True)
    study_word_id = Column(Integer, ForeignKey('Vocabs.id', ondelete='CASCADE'), nullable=True)
    wrong_word_id = Column(Integer, ForeignKey('Vocabs.id', ondelete='CASCADE'), nullable=True)
    correct_word_id = Column(Integer, ForeignKey('Vocabs.id', ondelete='CASCADE'), nullable=True)
    time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id}'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id}'
        return s

