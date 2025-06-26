import os
import sys
from dotenv import load_dotenv

# O caminho da pasta ONDE está o .exe (se for .exe) ou do script (em dev)
if getattr(sys, 'frozen', False):
    # Se está a correr como .exe (PyInstaller)
    exe_dir = os.path.dirname(sys.executable)
else:
    # Se está a correr em Python normal
    exe_dir = os.path.dirname(os.path.abspath(__file__))

# Garante que existe a pasta 'instance' ao lado do .exe
instance_dir = os.path.join(exe_dir, 'instance')
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

db_path = os.path.join(instance_dir, 'db.sqlite3')
print(">>>>> BASE DE DADOS USADA:", db_path)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_aqui'
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'icons')
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    SESSION_PERMANENT = False
