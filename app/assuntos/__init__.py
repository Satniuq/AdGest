# app/assuntos/__init__.py

from flask import Blueprint

# o único lugar onde o Blueprint é criado
assuntos_bp = Blueprint(
    'assuntos',
    __name__,
    url_prefix='/assuntos',
    template_folder='templates'
)

# Garante que tudo seja importado quando o módulo subir:
from app.assuntos import routes
from app.assuntos import models
from app.assuntos import forms
from app.assuntos import services

