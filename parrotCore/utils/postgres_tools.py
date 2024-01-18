from sqlalchemy import inspect
from configs.postgres_config import ENGINES, BASES, get_db_session


class DatabaseModelManager:

    def __init__(self, db, model_dic=None):
        if model_dic is None:
            model_dic = {}
        self.db = db
        self.model_dic = model_dic

    def get_tables(self):
        insp = inspect(ENGINES[self.db])
        return insp.get_table_names()

    def _create_table(self, table_name, abstract_model):
        if table_name not in self.model_dic:
            cls = type(table_name, (abstract_model,), {
                '__tablename__': table_name,
                '__table_args__': {
                    'extend_existing': True
                }
            })
            BASES[self.db].metadata.create_all()
            self.model_dic[table_name] = cls
        return self.model_dic[table_name]

    def use_table(self, table_name, abstract_model):
        model = self._create_table(table_name, abstract_model)
        return model

    def get_session(self):
        return get_db_session(self.db)


if __name__ == "__main__":
    for BASE in BASES.values():
        BASE.metadata.create_all()