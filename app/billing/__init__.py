#app/billing/__init__.py

from flask import Blueprint

billing_bp = Blueprint(
    'billing',
    __name__, 
    url_prefix='/billing',
    template_folder='templates',
)

from app.billing import routes  # noqa: F401
