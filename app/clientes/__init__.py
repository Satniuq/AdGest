#app/clientes/__init__.py

from flask import Blueprint

clientes_bp = Blueprint(
    'client',
    __name__,
    url_prefix='/clientes',
    template_folder='templates',
)

from app.clientes import routes  # noqa: F401
