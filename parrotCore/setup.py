from setuptools import setup, find_packages

PROJECT_NAME = 'prediction'
VERSION = '0.0.1'

setup(name=PROJECT_NAME,
      version=VERSION,
      entry_points={
          'console_scripts': [
              'manager = manager:main'
          ]
      },
      license='MIT',
      packages=find_packages(),
      install_requires=[
          'ujson==5.1.0',
          'redis==4.2.1',
          'requests==2.27.1',
          'aiohttp==3.8.1',
          'websocket-client==0.48.0',
          'flask==2.0.3',
          'werkzeug==2.3.6',
          'click==8.1.3',
          'itsdangerous==2.1.2',
          'jinjia2==3.1.2',
          'greenlet==1.1.2',
          'gevent==21.12.0',
          'pandas==1.4.1',
          'numpy==1.22.3',
          'fire==0.4.0',
          'python-crontab==2.6.0',
          'sqlalchemy==1.4.29',
          'joblib==1.1.0',
          'psycopg2-binary==2.9.3',
          'pytest==7.1.1',
          'pytest-order==1.0.1',
          'cryptography==3.4.7',
          'flask-cors==3.0.10',
          'simplejson==3.17.6',
          'cos-python-sdk-v5==1.9.17',
          'flask_socketio',
          'flask_session',
          'markupsafe',
          'python-engineio==4.4.0',
          'bidict',
          'pymysql==1.0.3',
          'setuptools==68.0.0',
          'zope',
          'Flask>=0.9',
          'crcmod',
          'dicttoxml',
          'pycryptodome',
          'requests>=2.8',
          'termcolor',
          'python-dateutil>=2.8.1',
          'blinker>=1.6.2',
          'importlib-metadata>=3.6.0',
      ],
      zip_safe=False
      )
