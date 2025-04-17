from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
import os
import json
from markupsafe import Markup

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SESSION_PERMANENT'] = False
    app.jinja_env.globals['timedelta'] = timedelta

    @app.before_request
    def make_session_non_permanent():
        session.permanent = False

    # Inicialização de extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'main.login'
    
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Disponibiliza getattr no ambiente Jinja
    app.jinja_env.globals['getattr'] = getattr
    # Disponibiliza hasattr para uso nos templates
    app.jinja_env.globals['hasattr'] = hasattr

    # Registro do filtro 'get_attr'
    def get_attr(obj, attr_name):
        try:
            return getattr(obj, attr_name)
        except AttributeError:
            return None
    app.jinja_env.filters['get_attr'] = get_attr

    # --- Definição do filtro personalizado render_snapshot com nomes amigáveis ---
    CAMPO_LABELS = {
        "nome_tarefa": "Nome",
        "descricao": "Descrição",
        "due_date": "Data de Vencimento",
        "sort_order": "Ordem",
        "is_completed": "Concluído",
        "horas": "Horas",
        "horas_adicionadas": "Horas Adicionadas",
        "total_horas": "Horas Totais"
    }

    def render_snapshot(value):
        """
        Converte uma string JSON ou um dicionário em uma lista HTML formatada com nomes amigáveis.
        
        Exemplo:
        {
            "nome_tarefa": {"old": "Antigo", "new": "Novo"},
            "due_date": {"old": "2025-04-01", "new": "2025-04-08"}
        }
        
        Será renderizado como:
        <ul style="list-style: none; padding-left: 0;">
            <li><strong>Nome:</strong> Antes: Antigo, Depois: Novo</li>
            <li><strong>Data de Vencimento:</strong> Antes: 2025-04-01, Depois: 2025-04-08</li>
        </ul>
        """
        # Se já for um dict, usa-o; caso contrário, tenta interpretar como JSON
        if isinstance(value, dict):
            data = value
        else:
            try:
                data = json.loads(value)
            except Exception:
                return value  # Se não for um JSON válido, retorna o valor original

        html = "<ul style='list-style: none; padding-left: 0;'>"
        for campo, alteracoes in data.items():
            # Busca um label amigável; se não houver, usa o próprio nome do campo
            label = CAMPO_LABELS.get(campo, campo)
            if isinstance(alteracoes, dict) and "old" in alteracoes and "new" in alteracoes:
                html += f"<li><strong>{label}:</strong> Antes: {alteracoes.get('old')}, Depois: {alteracoes.get('new')}</li>"
            else:
                html += f"<li><strong>{label}:</strong> {alteracoes}</li>"
        html += "</ul>"
        return Markup(html)

    app.jinja_env.filters['render_snapshot'] = render_snapshot
    # -----------------------------------------------------------

    
    # Configuração de logging
    # Se estiver em ambiente de desenvolvimento (DEBUG=True) ou não estiver no App Engine, cria log em arquivo.
    if app.config.get("DEBUG") or os.environ.get("GAE_INSTANCE") is None:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.info('Debug AdGest startup')
    else:
        # Em ambiente de produção (App Engine), não escrevemos logs em arquivo, pois o sistema é somente leitura.
        # O App Engine coleta o stdout/stderr automaticamente.
        app.logger.info('Production startup – logs will be sent to stdout')

    @app.context_processor
    def inject_today():
        from datetime import date
        return dict(today=date.today())
    
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.accounting import accounting as accounting_blueprint
    app.register_blueprint(accounting_blueprint, url_prefix='/accounting')

    return app
