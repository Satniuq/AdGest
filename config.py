import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_aqui'

    if FLASK_ENV == 'production':
        # Conexão TCP direta ao Cloud SQL via IP privada
        DB_USER = os.environ['DB_USER']
        DB_PASS = os.environ['DB_PASS']
        DB_HOST = os.environ['DB_HOST']
        DB_PORT = os.environ.get('DB_PORT', 3306)
        DB_NAME = os.environ['DB_NAME']
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        # Desenvolvimento local
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'db.sqlite3')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'icons')
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME') or 'user_imag'
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    SESSION_PERMANENT = False
