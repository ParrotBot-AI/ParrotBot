from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy_utils import database_exists, create_database
from configs.version import VERSION_ENV

if VERSION_ENV == 'local' or VERSION_ENV == 'dev':
    MYSQL_PORT_DEV = 19782
    MYSQL_HOST_DEV = 'yingwuzhixue.com'
    MYSQL_SETTINGS = {
        "core": {
            "HOST": MYSQL_HOST_DEV,
            "PORT": MYSQL_PORT_DEV,
            "USERNAME": "root",
            "PASSWORD": "Mysql-60003",
            "DB": "core",
            "CONNECTOR": "pymysql"
        }
    }


def get_db_uri(CONNECTOR, USERNAME, PASSWORD, HOST, PORT, DB):
    return f'mysql+{CONNECTOR}://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DB}'


def get_db_session_sql(db) -> Session:
    return sessionmaker(ENGINES[db], autocommit=False, autoflush=False)()


DB_URI = get_db_uri(**MYSQL_SETTINGS["core"])

ENGINES = {
    "core": create_engine(
        DB_URI,
        max_overflow=-1,
        pool_pre_ping=True,
        pool_recycle=3600)
}

if not database_exists(ENGINES['core'].url):
    create_database(ENGINES['core'].url)
    print(f"Database Created: {database_exists(ENGINES['core'].url)}")

BASES = {
    "core": declarative_base(ENGINES["core"])
}


