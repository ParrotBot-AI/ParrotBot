from configs.version import VERSION_ENV

if VERSION_ENV == 'local':
    REDIS_HOST = '1.94.23.138'
    REDIS_PORT = 19783
elif VERSION_ENV == 'dev':
    REDIS_HOST = '127.0.0.1'
    REDIS_PORT = 19783

REDIS_SETTINGS = {
    'test': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 0,
        'password': 'test'
    },
    'broker': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 2,
        'password': 'test'
    },
    'core_broker': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 3,
        'password': 'test'
    },
    'core_cache': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 4,
        'password': 'test'
    },
    'core_learning':{
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 5,
        'password': 'test'
    }
}
