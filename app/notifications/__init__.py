#app/notifications/__init__.py

from flask import Blueprint

notifications_bp = Blueprint(
    'notifications',
    __name__,
    url_prefix='/notifications',
    template_folder='templates'
)

from app.notifications import routes  # noqa: F401
