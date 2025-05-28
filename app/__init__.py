import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta, date

from flask import Flask, session, redirect, url_for, flash, request, jsonify
from flask_wtf.csrf import CSRFError
from markupsafe import Markup

from config import Config
from app.extensions import db, migrate, login_manager, mail, csrf
from app.auth.models import User
from app.utils import OFFICE_ROLES

def create_app():
    # --- CRIAÇÃO E CONFIGURAÇÃO DA APP ---
    flask_app = Flask(__name__, instance_relative_config=True)
    flask_app.config.from_object(Config)
    flask_app.config['SESSION_PERMANENT'] = False

    # --- SESSÃO NÃO-PERMANENTE ---
    @flask_app.before_request
    def make_session_non_permanent():
        session.permanent = False

    # --- JINJA GLOBALS & FILTERS ---
    flask_app.jinja_env.globals['timedelta'] = timedelta
    flask_app.jinja_env.globals['getattr']   = getattr
    flask_app.jinja_env.globals['hasattr']   = hasattr

    def get_attr(obj, attr_name):
        try:
            return getattr(obj, attr_name)
        except AttributeError:
            return None
    flask_app.jinja_env.filters['get_attr'] = get_attr

    CAMPO_LABELS = {
        "nome_tarefa":      "Nome",
        "descricao":        "Descrição",
        "due_date":         "Data de Vencimento",
        "sort_order":       "Ordem",
        "is_completed":     "Concluído",
        "horas":            "Horas",
        "horas_adicionadas":"Horas Adicionadas",
        "total_horas":      "Horas Totais"
    }

    def render_snapshot(value):
        if isinstance(value, dict):
            data = value
        else:
            try:
                data = json.loads(value)
            except Exception:
                return value

        html = "<ul style='list-style: none; padding-left: 0;'>"
        for campo, alter in data.items():
            label = CAMPO_LABELS.get(campo, campo)
            if isinstance(alter, dict) and "old" in alter and "new" in alter:
                html += (
                    f"<li><strong>{label}:</strong> Antes: {alter['old']}, "
                    f"Depois: {alter['new']}</li>"
                )
            else:
                html += f"<li><strong>{label}:</strong> {alter}</li>"
        html += "</ul>"
        return Markup(html)

    flask_app.jinja_env.filters['render_snapshot'] = render_snapshot

    # --- LOGGING ---
    if flask_app.config.get("DEBUG") or os.environ.get("GAE_INSTANCE") is None:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        handler.setLevel(logging.INFO)
        flask_app.logger.addHandler(handler)
        flask_app.logger.info('Debug AdGest startup')
    else:
        flask_app.logger.info('Production startup – logs to stdout')

    # --- INICIALIZAÇÃO DAS EXTENSÕES ---
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)
    mail.init_app(flask_app)
    csrf.init_app(flask_app)

    # ─── SESSÃO SERVER-SIDE ───
    from flask_session import Session

    # Usa flask_app.config['ENV'], que vale "development" ou "production"
    if flask_app.config.get('ENV') == 'production':
        flask_app.config['SESSION_TYPE'] = 'sqlalchemy'
        flask_app.config['SESSION_SQLALCHEMY'] = db
    else:
        flask_app.config['SESSION_TYPE'] = 'filesystem'

    # Configurações comuns
    flask_app.config['SESSION_PERMANENT'] = False
    flask_app.config['SESSION_USE_SIGNER'] = True

    # Inicializa o session store
    Session(flask_app)

    # Garante que a tabela 'session' existe no DB (CREATE IF NOT EXISTS)
    with flask_app.app_context():
        db.create_all()


    @flask_app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        # se for AJAX, devolve JSON 400
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(error=e.description), 400
        # senão, flash + redirect normal
        flash(e.description, 'danger')
        return redirect(url_for('auth.login'))

    # --- FORÇA CARREGAMENTO DE MODELS PARA QUE RELATIONSHIPS FUNCIONEM ---
    with flask_app.app_context():
        import app.auth.models
        import app.clientes.models
        import app.assuntos.models
        import app.processos.models
        import app.prazos.models
        import app.tarefas.models
        import app.billing.models

    # --- FLASK-LOGIN CONFIG ---
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- INJETAR HOJE E NOTIFICAÇÕES DIRETO EM jinja_env.globals ---

    # 1) hoje
    flask_app.jinja_env.globals['today'] = date.today

    # 2) notificações
    def _get_notifications():
        from flask_login import current_user
        if current_user.is_authenticated:
            from app.notifications.models import Notification
            notifs = (
                Notification.query
                .filter_by(user_id=current_user.id, is_read=False)
                .order_by(Notification.timestamp.desc())
                .all()
            )
            return notifs
        return []

    @flask_app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from app.notifications.models import Notification

        if current_user.is_authenticated:
           # somente não-lidas
           notifs = (
               Notification.query
               .filter_by(user_id=current_user.id, is_read=False)
               .order_by(Notification.timestamp.desc())
               .all()
           )
           # contador igual ao tamanho da lista
           unread = len(notifs)
        else:
            notifs = []
            unread = 0

        return {
            'notifications': notifs,      # lista
            'unread_count': unread       # inteiro
        }

    # --- REGISTRO DE BLUEPRINTS ---
    from app.auth             import auth_bp
    from app.dashboard        import dashboard_bp
    from app.index            import index_bp
    from app.dashboard_prazos import dashboard_prazos_bp
    from app.assuntos         import assuntos_bp
    from app.tarefas          import tarefas_bp
    from app.prazos           import prazos_bp
    from app.processos        import processos_bp
    from app.clientes         import clientes_bp
    from app.billing          import billing_bp
    from app.notifications    import notifications_bp
    from app.accounting       import accounting as accounting_bp


    flask_app.register_blueprint(index_bp)
    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(dashboard_bp)
    flask_app.register_blueprint(dashboard_prazos_bp)
    flask_app.register_blueprint(assuntos_bp)
    flask_app.register_blueprint(tarefas_bp)
    flask_app.register_blueprint(prazos_bp)
    flask_app.register_blueprint(processos_bp)
    flask_app.register_blueprint(clientes_bp)
    flask_app.register_blueprint(billing_bp)
    flask_app.register_blueprint(notifications_bp)
    flask_app.register_blueprint(accounting_bp, url_prefix='/accounting')


    @flask_app.route('/favicon.ico')
    def favicon():
        return flask_app.send_static_file('icons/icon-192x192.png')

    return flask_app
