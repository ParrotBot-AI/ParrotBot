from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy import UniqueConstraint
from configs.environment import DATABASE_SELECTION

# from blueprints.education.models import (Exams)

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import BASES
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import BASES


class Users(BASES['core']):
    __tablename__ = "Users"
    # __table_args__ = (
    #     {"extend_existing":True,'mysql_charset': 'utf8',}
    # )
    __table_args__ = (
        UniqueConstraint("user_id"),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(Integer, nullable=False)
    age = Column(Integer, nullable=True)
    school = Column(String(30), nullable=True)
    region = Column(String(20), nullable=True)
    task_complete = Column(Integer, default=0)
    vocab_level = Column(String(6), nullable=True)
    total_study_days = Column(Integer, default=0)
    user_plan = Column(Integer, default=0)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} p: {self.user_id} a: {self.age})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} p: {self.user_id} a: {self.age})'
        return s


class Accounts(BASES['core']):
    __tablename__ = "Accounts"
    # __table_args__ = (
    #     {"extend_existing":True,'mysql_charset': 'utf8',}
    # )

    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(Integer, ForeignKey('Users.id', ondelete='CASCADE'), nullable=False)
    # exam_id = Column(Integer, nullable=False)
    exam_id = Column(Integer, ForeignKey('Exams.id', ondelete='CASCADE'), nullable=False)
    model_today_used = Column(Integer, default=0)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)
    last_request_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} p: {self.user_id} e: {self.exam_id})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} p: {self.user_id} e: {self.exam_id})'
        return s


class AccountsVocab(BASES['core']):
    __tablename__ = "account_vocab"
    account_id = Column(Integer, primary_key=True)
    config_link = Column(String(20))  # redis key "user_id:account_id:"

    def __str__(self) -> str:
        s = f'(A: {self.account_id} C: {self.config_link}'
        return s

    def __repr__(self) -> str:
        s = f'(A: {self.account_id} C: {self.config_link}'
        return s


class AccountsScores(BASES['core']):
    __tablename__ = "account_scores"

    account_id = Column(Integer, primary_key=True)
    config_link = Column(String(20))  # redis key "vocab:user_id"

    def __str__(self) -> str:
        s = f'(A: {self.account_id} C: {self.config_link}'
        return s

    def __repr__(self) -> str:
        s = f'(A: {self.account_id} C: {self.config_link}'
        return s


if __name__ == "__main__":
    for BASE in BASES.values():
        BASE.metadata.create_all()
