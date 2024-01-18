from configs.mysql_config import get_db_session_sql

with get_db_session_sql('predict') as session:
    session.execute("""
        SET foreign_key_checks = 0;
      """)
    session.execute("""
    SELECT CONCAT('DROP TABLE ', TABLE_NAME, ';')
    FROM INFORMATION_SCHEMA.tables
    WHERE TABLE_SCHEMA = 'Prediction_manage';
  """)
    session.execute("""
            SET foreign_key_checks = 1;
          """)
    try:
        session.commit()
        print('All table dropped.')
    except Exception as e:
        session.rollback()
        raise e

from blueprints.dataApi.models import *

for BASE in BASES.values():
    BASE.metadata.create_all()

print('All table recreated.')
