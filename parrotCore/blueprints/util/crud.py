import datetime
from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session


class crudController:
    """
    通用crud controller
    """
    default_not_show = ['create_time', 'last_update_time']

    def _create(self, model, create_params, restrict_field=None, callback_function=None):
        # # Example usage:
        # params = {
        #     'account_id': 123,
        #     'symbol': 'cash',
        #     'amount': INIT_CASH,
        #     'is_locked': False
        # }
        with db_session('core') as session:
            if restrict_field:
                old_record = (
                    session.query(model)
                    .filter(getattr(model, restrict_field) == create_params[restrict_field])
                    .one_or_none()
                )
                if old_record is None:
                    default_dic = {
                        'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                        'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                    }
                    merged_dict = {**default_dic, **create_params}
                    record = model(**merged_dict)
                    session.add(record)
                else:
                    return False, "已存在"

            else:
                default_dic = {
                    'create_time': datetime.datetime.now(tz=datetime.timezone.utc),
                    'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)
                }
                merged_dict = {**create_params, **default_dic}
                record = model(**merged_dict)
                session.add(record)

            if callback_function is not None:
                callback_function()

            try:
                session.commit()
                return True, ""
            except Exception as e:
                session.rollback()
                return False, str(e)

    def _retrieve(self, model, restrict_field, restrict_value, callback_function=None):  # "id", 5
        with db_session('core') as session:
            record = (
                session.query(model)
                .filter(getattr(model, restrict_field) == restrict_value)
                .one_or_none()
            )

            if callback_function is not None:
                callback_function()

            if record:
                return record
            else:
                return None

    def _update(self, model, update_parameters, restrict_field, callback_function=None):
        with db_session('core') as session:
            # update_dic = {col: getattr(update_parameters, col) for col in
            #               [column.key for column in self.Model.__table__.columns] if
            #               col != 'id'}
            default_dic = {'last_update_time': datetime.datetime.now(tz=datetime.timezone.utc)}

            records = (
                session.query(model)
                .filter(getattr(model, restrict_field) == update_parameters[restrict_field])
                .update({**update_parameters, **default_dic})
            )

            if callback_function is not None:
                callback_function()

            try:
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                return False

    def _delete(self, model, restrict_field, restrict_value):
        with db_session('core') as session:
            record = (
                session.query(model)
                .filter(getattr(model, restrict_field) == restrict_value)
                .one_or_none()
            )
            if record:
                session.delete(record)
                try:
                    session.commit()
                    return True
                except Exception as e:
                    session.rollback()
                    return e


if __name__ == '__main__':
    pass