from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

MYSQL_SETTINGS = {
    "predict": {
        "HOST": "localhost",
        "PORT": 3306,
        "USERNAME": "root",
        "PASSWORD": "Mysql-60003",
        "DB": "Prediction_manage",
        "CONNECTOR": "pymysql"
    }
}


def get_db_uri(CONNECTOR, USERNAME, PASSWORD, HOST, PORT, DB):
    return f'mysql+{CONNECTOR}://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DB}'


def get_db_session_sql(db) -> Session:
    return sessionmaker(ENGINES[db], autocommit=False)()


DB_URI_CORPUS = get_db_uri(**MYSQL_SETTINGS["predict"])

ENGINES = {
    "predict": create_engine(DB_URI_CORPUS,
                             max_overflow=-1,
                             pool_pre_ping=True,
                            pool_recycle=3600)
}

BASES = {
    "predict": declarative_base(ENGINES["predict"])
}


