from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Verifica se já existe um usuário "admin"
    admin = User.query.filter_by(username='admin').first()
    if admin is None:
        admin = User(
            username='admin',
            nickname='ADM',  # ou outro nickname curto desejado
            email='admin@example.com',
            password=generate_password_hash('admin 1'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado com sucesso.")
    else:
        print("Usuário admin já existe.")
