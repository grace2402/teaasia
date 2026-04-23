import os
from datetime import datetime


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-to-a-real-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'skuvy.liang@nextdrive.io'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or ''
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    FLASKY_MAIL_SUBJECT_PREFIX = '[TeaAsia]'
    FLASKY_MAIL_SENDER = 'TeaAsia Admin <skuvy.liang@nextdrive.io>'

    CONFLUENCE = {
        'BASE_URL': os.environ.get('CONFLUENCE_BASE_URL') or '',
        'EMAIL': os.environ.get('CONFLUENCE_EMAIL') or '',
        'API_TOKEN': os.environ.get('CONFLUENCE_API_TOKEN') or '',
        'SPACE_KEY': os.environ.get('CONFLUENCE_SPACE_KEY') or '',
        'PARENT_ID': os.environ.get('CONFLUENCE_PARENT_ID') or 0,
    }

    P_IMAGEPATH = os.environ.get('P_IMAGEPATH') or '/app/static/images/products/'
    S_IMAGEPATH = os.environ.get('S_IMAGEPATH') or '/app/static/images/stories/'
    UPLOADPATH = os.environ.get('UPLOADPATH') or '/app/uploads/'
    UPLOADED_IMAGES_DEST = os.environ.get('UPLOADED_IMAGES_DEST') or '/app/static/images/'

    ND_TOKEN = 'hemstw-i-am-hemstw'

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'postgresql://postgres:zuxfbolahnkagwwl@localhost:5433/teaasia'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'postgresql://postgres:zuxfbolahnkagwwl@localhost:5433/teaasia_test'


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:zuxfbolahnkagwwl@localhost:5433/teaasia'


class StagingConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('STAGING_DATABASE_URL') or \
        'postgresql://postgres:zuxfbolahnkagwwl@localhost:5433/teaasia_staging'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'staging': StagingConfig,
    'default': DevelopmentConfig,
}


# Module-level exports for direct import (e.g., `from config import P_IMAGEPATH`)
P_IMAGEPATH = os.environ.get('P_IMAGEPATH') or '/app/static/images/products/'
S_IMAGEPATH = os.environ.get('S_IMAGEPATH') or '/app/static/images/stories/'
UPLOADPATH = os.environ.get('UPLOADPATH') or '/app/uploads/'
