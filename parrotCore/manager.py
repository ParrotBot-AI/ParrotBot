from utils import abspath
from utils.logger_tools import get_general_logger
from utils.manager_tools import ServiceManager
import fire

logger = get_general_logger(name='manager', path=abspath('logs'))


class DataApi(ServiceManager):
    name = 'ParrotCore'
    file = 'core_web.py'
    dir_path = abspath('services')


class Streaming(ServiceManager):
    name = 'ParrotCoreStream'
    file = 'core_stream.py'
    dir_path = abspath('services')


class VocabService(ServiceManager):
    name = 'ParrotCoreVocab'
    file = 'core_vocabs.py'
    dir_path = abspath('services')
    schedule = '1 0 * * *'
    time_zone = "Asia/Shanghai"


SERVICES_MAP = {
    'ParrotCore': DataApi,
    'ParrotCoreStream': Streaming,
    'ParrotCoreVocab': VocabService
}


def run_service(service_name, action):
    """
    action: start | stop | run | enable | disable | status
    """
    if service_name not in SERVICES_MAP:
        print(f'No such service: {service_name}')
        return

    service = SERVICES_MAP[service_name]
    service(action=action)


def main():
    fire.Fire(run_service)


if __name__ == '__main__':
    main()
