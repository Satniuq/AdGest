# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate    import Migrate
from flask_login      import LoginManager
from flask_mail       import Mail
from flask_wtf        import CSRFProtect

db            = SQLAlchemy()
migrate       = Migrate()
login_manager = LoginManager()
mail          = Mail()
csrf          = CSRFProtect()
