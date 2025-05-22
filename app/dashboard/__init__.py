#app/dashboard/__init__.py

from flask import Blueprint

dashboard_bp = Blueprint(
    'dashboard',
    __name__,
    url_prefix='/dashboard',
    template_folder='templates',
    static_folder='static',
)

from app.dashboard import routes  # noqa: F401
