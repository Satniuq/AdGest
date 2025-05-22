# app/index/__init__.py

from flask import Blueprint

# nota: url_prefix='' faz com que este blueprint sirva na raiz '/'
index_bp = Blueprint(
    'index',
    __name__,
    template_folder='templates',
    url_prefix=''
)

from app.index import routes  # noqa: F401
