#app/accounting/__init__.py

from flask import Blueprint

accounting = Blueprint(
    'accounting',
    __name__,
    url_prefix='/accounting',
    template_folder='templates'
)

from app.accounting import routes

