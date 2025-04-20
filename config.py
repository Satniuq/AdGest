import os
from dotenv import load_dotenv

# Determina o diretório base e carrega .env em dev
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# Ambiente: 'production' ou 'development'
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

class Config:
    # Chave secreta da aplicação
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_aqui'

    # Configuração do banco de dados
    if FLASK_ENV == 'production':
        # Em produção, montamos a URI MySQL via TCP usando IP privado
        DB_USER = os.environ.get('DB_USER')
        DB_PASS = os.environ.get('DB_PASS')
        DB_HOST = os.environ.get('DB_HOST')
        DB_PORT = os.environ.get('DB_PORT', 3306)
        DB_NAME = os.environ.get('DB_NAME')
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASS}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        # Em desenvolvimento, usamos SQLite local
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'db.sqlite3')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pasta para uploads locais (dev)
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'icons')

    # Bucket GCS (produção)
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME') or 'user_imag'

    # Configuração de e‑mail
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    # Sessões não permanentes: cookie expira ao fechar o navegador
    SESSION_PERMANENT = False
