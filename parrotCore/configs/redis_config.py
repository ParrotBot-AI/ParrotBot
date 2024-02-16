from configs.version import VERSION_ENV

if VERSION_ENV == 'local':
    REDIS_PORT = 6379
elif VERSION_ENV == 'dev':
    REDIS_PORT = 19783

REDIS_SETTINGS = {
    'test': {
        'host': '127.0.0.1',
        'port': REDIS_PORT,
        'db': 0,
        'password': 'test'
    },
    'broker': {
        'host': '127.0.0.1',
        'port': REDIS_PORT,
        'db': 2,
        'password': 'test'
    },
    'core_broker': {
        'host': '127.0.0.1',
        'port': REDIS_PORT,
        'db': 3,
        'password': 'test'
    },
    'core_cache': {
        'host': '127.0.0.1',
        'port': REDIS_PORT,
        'db': 4,
        'password': 'test'
    }
}
