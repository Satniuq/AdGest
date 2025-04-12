import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_aqui'
    
    # A string de conexão será definida através da variável de ambiente DATABASE_URL.
    # Em desenvolvimento, se DATABASE_URL não estiver definida, você pode optar por usar SQLite;
    # mas para produção, defina essa variável.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'icons')
    
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'jose.quintas1994@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'enmeuscbdsxdjcpx'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'jose.quintas1994@gmail.com'
