import os
from flask import Flask
from blueprints import account, education, learning
from flask_cors import CORS
from sqlalchemy.ext.declarative import declarative_base
from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == "postgre":
    from configs.postgre_config import DB_URI, ENGINES, BASES
elif DATABASE_SELECTION == "mysql":
    from configs.mysql_config import DB_URI, ENGINES, BASES


# choose apps from blueprints to register
def register_blueprints(app: Flask):
    app.register_blueprint(account.bp)
    app.register_blueprint(education.bp)
    app.register_blueprint(learning.bp)


def create_app(test_config=None):
    # create and configure the apps
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        SQLALCHEMY_DATABASE_URI=DB_URI,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    app.config["JSON_AS_ASCII"] = False

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    register_blueprints(app)
    CORS(app)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
