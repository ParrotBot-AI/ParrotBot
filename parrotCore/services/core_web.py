import sys
import os

root_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(root_path, '..')
sys.path.append(project_root)
from gevent import monkey
from gevent.pywsgi import WSGIServer

monkey.patch_all()

from apps import app
from utils import abspath
from utils.logger_tools import get_general_logger
from configs.management_app_config import HOST, PORT

logger = get_general_logger(name='core', path=abspath('logs'))


def main():
    _app = app.create_app()
    # apps.run(debug=True, port=10981, host='0.0.0.0')
    http_server = WSGIServer((HOST, PORT), _app)
    logger.info('Core Started.')
    logger.info(f'Host: {HOST} Port: {PORT} URL: http://{HOST}:{PORT}')
    http_server.serve_forever()


if __name__ == '__main__':
    main()
