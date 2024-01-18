from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy_utils import database_exists, create_database

POSTGRES_SETTINGS = {
    "core": {
        "HOST": "localhost",
        "PORT": 5432,
        "USERNAME": "postgres",
        "PASSWORD": "9d36SkmzYV3#dssblr34b",
        "DB": "core",
        "CONNECTOR": "psycopg2"
    }
}


def get_db_uri(CONNECTOR, USERNAME, PASSWORD, HOST, PORT, DB):
    return f'postgresql+{CONNECTOR}://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DB}'


def get_db_session(db) -> Session:
    return sessionmaker(ENGINES[db])()


DB_URI_UFA = get_db_uri(**POSTGRES_SETTINGS["core"])

ENGINES = {
    "core": create_engine(DB_URI_UFA, max_overflow=-1)
}

if not database_exists(ENGINES['core'].url):
    create_database(ENGINES['core'].url)
    print(f"Database Created: {database_exists(ENGINES['core'].url)}")

BASES = {
    "core": declarative_base(ENGINES["core"])
}
