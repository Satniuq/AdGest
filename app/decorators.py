from functools import wraps
from flask import abort, current_app, flash, redirect, url_for
from flask_login import current_user
from app import db

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Supondo que o papel "admin" seja necessário; ajuste conforme sua lógica.
        if current_user.role != 'admin':
            abort(403)  # Acesso proibido
        return f(*args, **kwargs)
    return decorated_function

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def role_required(allowed_roles):
    """
    Permite acesso se o usuário tiver um papel permitido ou for admin.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.role != 'admin' and current_user.role not in allowed_roles:
                flash('Acesso negado. Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def handle_db_errors(f):
    """
    Decorador para capturar exceções de operações com o banco de dados, 
    realizar rollback, logar o erro e exibir uma mensagem flash para o usuário.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            # Executa a função original
            return f(*args, **kwargs)
        except Exception as e:
            # Em caso de erro, desfaz as alterações no banco
            db.session.rollback()
            # Registra o erro no log da aplicação
            current_app.logger.error(f'Erro na função {f.__name__}: {str(e)}')
            # Exibe uma mensagem flash de erro para o usuário
            flash(f'Ocorreu um erro: {str(e)}', 'danger')
            # Redireciona para uma rota de fallback; aqui, estamos usando o dashboard
            return redirect(url_for('dashboard.dashboard'))
    return wrapper