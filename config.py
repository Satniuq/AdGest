import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# Carrega o arquivo .env localizado na raiz do projeto
load_dotenv(os.path.join(basedir, '.env'))

# Define o ambiente: 'production' para produção, 'development' para desenvolvimento
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

class Config:
    # Chave secreta da aplicação
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_aqui'
    
    # Configuração do banco de dados
    # Se estiver em produção (FLASK_ENV == 'production'), use o Cloud SQL; caso contrário, use um banco de dados local (SQLite, por exemplo).
    if FLASK_ENV == 'production':
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'mysql+pymysql://db-adgest1:Sporting789@/adgest_db?unix_socket=/cloudsql/adgest:us-central1:db-adgest1'
    else:
        # No ambiente de desenvolvimento, usamos um SQLite local por simplicidade.
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'db.sqlite3')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Pasta para uploads locais (usada para desenvolvimento, se necessário)
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'icons')
    
    # Configuração do Google Cloud Storage – para produção, essa variável deve conter o nome do bucket.
    # Em desenvolvimento, você pode manter o mesmo ou configurar outro bucket de teste.
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME') or 'user_imag'
    
    # Configuração de e-mail
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'jose.quintas1994@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'enmeuscbdsxdjcpx'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'jose.quintas1994@gmail.com'
