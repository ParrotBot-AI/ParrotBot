from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Float
from configs.environment import DATABASE_SELECTION

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


class TaskFlows(BASES['core']):
    __tablename__ = "TaskFlows"

    id = Column(Integer, autoincrement=True, primary_key=True)
    task_id = Column(Integer, ForeignKey('Tasks.id', ondelete='CASCADE'), nullable=False)
    from_module_id = Column(Integer, ForeignKey('Modules.id', ondelete='CASCADE'), nullable=True)
    to_module_id = Column(Integer, ForeignKey('Modules.id', ondelete='CASCADE'), nullable=True)
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


class TaskAccount(BASES['core']):
    __tablename__ = "TaskAccounts"

    id = Column(Integer, autoincrement=True, primary_key=True)
    account_id = Column(Integer, ForeignKey('Accounts.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, ForeignKey('Tasks.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    is_complete = Column(Boolean, default=False)
    complete_percentage = Column(Float, default=0)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id} t: {self.task_id})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} a: {self.account_id} t: {self.task_id})'
        return s
