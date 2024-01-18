# set up the response type

class BaseHttpResponse(dict):
    msg = 'default response'
    code = 10000
    data = {}

    def __init__(self, msg=None, code=None, data=None):
        if code:
            self.code = code
        if msg:
            self.msg = msg
        if data:
            self.data = data

        self['code'] = self.code
        self['msg'] = self.msg
        self['data'] = self.data

    def __str__(self):
        return f"code: {self.code}, msg: {self.msg}"


class SuccessDataResponse(BaseHttpResponse):
    msg = ''

    def __init__(self, data):
        self.data = data
        super().__init__()


class ArgumentExceptionResponse(BaseHttpResponse):
    msg = 'Insufficient or wrong arguments, please check the document.'
    code = 10001