#app/prazos/__init__.py

from flask import Blueprint

prazos_bp = Blueprint(
    'prazos',
    __name__,
    template_folder='templates/prazos',
    url_prefix='/prazos'
)

from app.prazos import routes  # noqa: F401