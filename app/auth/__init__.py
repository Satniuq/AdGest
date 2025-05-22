#app/auth/__init__.py

from flask import Blueprint

auth_bp = Blueprint(
    'auth',
    __name__,
    url_prefix='/auth',
    template_folder='templates'
)

# importa as rotas para registrar no blueprint
from app.auth import routes  # noqa: F401
