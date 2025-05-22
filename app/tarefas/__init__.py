#app/tarefas/__init__.py

from flask import Blueprint

# 1) cria o blueprint
tarefas_bp = Blueprint(
    'tarefas',
    __name__,
    url_prefix='/tarefas',
    template_folder='templates'
)

# Expõe as peças do módulo:
from app.tarefas import routes
from app.tarefas import models
from app.tarefas import forms
from app.tarefas import services
