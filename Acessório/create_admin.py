from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin is None:
        admin = User(
            username='admin',
            nickname='ADM',  # ou outro nickname de sua escolha
            email='admin@example.com',
            password=generate_password_hash('admin1'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado com sucesso.")
    else:
        print("Usuário admin já existe.")
