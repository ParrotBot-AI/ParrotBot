# REDIS_PORT_DEV = 19783
REDIS_PORT_DEV = 6379

REDIS_SETTINGS = {
  'test': {
    'host': '127.0.0.1',
    'port': REDIS_PORT_DEV,
    'db': 0,
    'password': 'test'
  },
  'broker': {
    'host': '127.0.0.1',
    'port': REDIS_PORT_DEV,
    'db': 2,
    'password': 'test'
  },
  'core_broker': {
    'host': '127.0.0.1',
    'port': REDIS_PORT_DEV,
    'db': 3,
    'password': 'test'
  },
  'core_cache':{
    'host': '127.0.0.1',
    'port': REDIS_PORT_DEV,
    'db': 4,
    'password': 'test'
  }
}