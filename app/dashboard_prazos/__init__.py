#app/prazos/dashboard_prazos.py

from flask import Blueprint

dashboard_prazos_bp = Blueprint(
    'dashboard_prazos',
    __name__,
    template_folder='templates',
    url_prefix='/prazos/manage'
)

from app.dashboard_prazos import routes  # noqa: F401