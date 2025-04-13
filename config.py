import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Substitua 'sua_chave_secreta_aqui' por uma chave forte (você pode gerar uma com: python -c "import secrets; print(secrets.token_hex(16))")
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_aqui'
    
    # Conexão com o Cloud SQL via socket Unix, lendo a variável de ambiente DATABASE_URL.
    # Em produção, DATABASE_URL deverá estar definida (veja o app.yaml).
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://db-adgest1:Sporting789@/adgest_db?unix_socket=/cloudsql/adgest:us-central1:db-adgest1'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'icons')
    
     # Configuração do Google Cloud Storage (usada para armazenar os arquivos de imagem em produção)
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME') or 'user_imag'

    # Configuração de em-mail
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'jose.quintas1994@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'enmeuscbdsxdjcpx'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'jose.quintas1994@gmail.com'
