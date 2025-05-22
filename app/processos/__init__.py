#App/processos/__init__.py

from flask import Blueprint

processos_bp = Blueprint(
    'processos',
    __name__,
    template_folder='templates',
    url_prefix='/processos'
)

from app.processos import routes  # noqa: F401
