# No __init__.py do accounting (sem template_folder)
from flask import Blueprint

accounting = Blueprint('accounting', __name__)

from app.accounting import routes

