# app/auth/models.py

from datetime import datetime
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from flask_login import UserMixin
from sqlalchemy.orm import relationship, backref
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    nickname = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_image = db.Column(db.String(120), default='default.jpg')
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='advogado')

    __table_args__ = (
        db.UniqueConstraint('email', name='uq_users_email'),
    )

    # prazos criados
    created_prazos = relationship(
        'PrazoJudicial',
        back_populates='owner',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # processos liderados
    led_processes = relationship(
        'Processo',
        back_populates='lead_attorney',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # pedidos de partilha (ClientShare)
    client_shares = relationship(
        'ClientShare',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # clientes que me foram partilhados (M:N via client_shares)
    shared_clients = relationship(
        'Client',
        secondary='client_shares',   # passa a usar client_shares em vez de shared_clients
        back_populates='shared_with',
        lazy='dynamic'
    )

    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=3600):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expires_sec)
            return User.query.get(data.get('user_id'))
        except Exception:
            return None

    def __repr__(self):
        return f'<User {self.username}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)

    user = relationship(
        'User',
        backref=backref('audit_logs', lazy='dynamic')
    )

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_id} at {self.timestamp}>'
