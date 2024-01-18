from sqlalchemy.inspection import inspect

class Serializer(object):
    @staticmethod
    def serialize(item, res):
        if not res:
            return {c: getattr(item, c) for c in inspect(item).attrs.keys()}
        else:
            return {c: getattr(item, c) for c in inspect(item).attrs.keys() if c not in res}

    @staticmethod
    def serialize_list(l, res=None):
        return [Serializer.serialize(m, res) for m in l]