import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.auth.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin is None:
        admin = User(
            username='admin',
            nickname='ADM',
            email='admin@example.com',
            password=generate_password_hash('admin_23'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado com sucesso.")
    else:
        print("Usuário admin já existe.")
