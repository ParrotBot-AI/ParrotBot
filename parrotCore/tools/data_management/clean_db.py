from configs.environment import DATABASE_SELECTION
if DATABASE_SELECTION == "postgre":
    from configs.postgre_config import get_db_session
elif DATABASE_SELECTION == "mysql":
    from configs.mysql_config import get_db_session_sql, MYSQL_SETTINGS
from sqlalchemy.sql import text

if DATABASE_SELECTION == "postgre":
    with get_db_session('core') as session:
        session.execute(text("""
        DO $$ DECLARE
          r RECORD;
        BEGIN
          FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = current_schema()) LOOP
            EXECUTE 'DROP TABLE ' || quote_ident(r.tablename) || ' CASCADE';
          END LOOP;
        END $$;
      """))
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
elif DATABASE_SELECTION == "mysql":
    with get_db_session_sql('core') as session:
        session.execute(text(f"""
            SET foreign_key_checks = 0;
          """))
        session.execute(text(f"""
        SELECT CONCAT('DROP TABLE ', TABLE_NAME, ';')
        FROM INFORMATION_SCHEMA.tables
        WHERE TABLE_SCHEMA = '{MYSQL_SETTINGS['core']['DB']}';
      """))
        session.execute(text("""
                SET foreign_key_checks = 1;
              """))
        try:
            session.commit()
            print('All table dropped.')
        except Exception as e:
            session.rollback()
            raise e

from blueprints.account.models import BASES as A_BASES
from blueprints.education.models import BASES as E_BASES
from blueprints.learning.models import BASES as L_BASES

for BASE in A_BASES.values():
    BASE.metadata.create_all()

for BASE in E_BASES.values():
    BASE.metadata.create_all()

for BASE in L_BASES.values():
    BASE.metadata.create_all()

print('All table recreated.')
