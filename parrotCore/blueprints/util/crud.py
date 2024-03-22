from datetime import datetime, timezone, timedelta, date
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

    def _create(self, model, create_params, restrict_field=None, callback_function=None, session=None):
        # # Example usage:
        # params = {
        #     'account_id': 123,
        #     'symbol': 'cash',
        #     'amount': INIT_CASH,
        #     'is_locked': False
        # }
        if session:
            if restrict_field:
                old_record = (
                    session.query(model)
                    .filter(getattr(model, restrict_field) == create_params[restrict_field])
                    .one_or_none()
                )
                if old_record is None:
                    default_dic = {
                        'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

,
                        'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


                    }
                    merged_dict = {**default_dic, **create_params}
                    record = model(**merged_dict)
                    session.add(record)
                else:
                    return False, "已存在"

            else:
                default_dic = {
                    'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

,
                    'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


                }
                merged_dict = {**create_params, **default_dic}
                record = model(**merged_dict)
                session.add(record)

            if callback_function is not None:
                callback_function()
            return True, record.id
        else:
            with db_session('core') as session:
                if restrict_field:
                    old_record = (
                        session.query(model)
                        .filter(getattr(model, restrict_field) == create_params[restrict_field])
                        .one_or_none()
                    )
                    if old_record is None:
                        default_dic = {
                            'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

,
                            'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


                        }
                        merged_dict = {**default_dic, **create_params}
                        record = model(**merged_dict)
                        session.add(record)
                    else:
                        return False, "已存在"

                else:
                    default_dic = {
                        'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

,
                        'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


                    }
                    merged_dict = {**create_params, **default_dic}
                    record = model(**merged_dict)
                    session.add(record)

                if callback_function is not None:
                    callback_function()

                try:
                    session.commit()
                    # session.close()
                    return True, record.id
                except Exception as e:
                    session.rollback()
                    # session.close()
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
                # session.close()
                return record
            else:
                # session.close()
                return None

    def _update(self, model, update_parameters, restrict_field, callback_function=None):
        with db_session('core') as session:
            default_dic = {'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))}

            records = (
                session.query(model)
                .filter(getattr(model, restrict_field) == update_parameters[restrict_field])
                .update({**update_parameters, **default_dic})
            )

            if callback_function is not None:
                callback_function()

            try:
                session.commit()
                session.close()
                return True, "Ok"
            except Exception as e:
                session.rollback()
                session.close()
                return False, "更新失败"

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
                    # session.close()
                    return True
                except Exception as e:
                    session.rollback()
                    # session.close()
                    return e


if __name__ == '__main__':
    pass
