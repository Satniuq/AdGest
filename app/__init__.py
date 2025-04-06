from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.globals['timedelta'] = timedelta

    # Inicialização de extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = 'main.login'
    
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Disponibiliza getattr no ambiente Jinja
    app.jinja_env.globals['getattr'] = getattr

    login_manager.login_view = 'main.login'
    
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Configuração de logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Debug AdGest startup')

    @app.context_processor
    def inject_today():
        from datetime import date
        return dict(today=date.today())
    
    # --- Definição do filtro personalizado ---
    def get_attr(obj, attr_name):
        try:
            return getattr(obj, attr_name)
        except AttributeError:
            return None

    # Adiciona o filtro à instância global do Jinja2
    app.jinja_env.filters['get_attr'] = get_attr
    # ---------------------------------------

    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.accounting import accounting as accounting_blueprint
    app.register_blueprint(accounting_blueprint, url_prefix='/accounting')

    return app
