# app/notifications/models.py

import json
from datetime import datetime
from app import db

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    extra_data = db.Column(db.Text, nullable=True)

    @property
    def extra(self):
        try:
            return json.loads(self.extra_data) if self.extra_data else {}
        except ValueError:
            return {}


class Comment(db.Model):
    __tablename__ = 'comments'
    id           = db.Column(db.Integer, primary_key=True)
    object_type  = db.Column(db.String(50), nullable=False)   # e.g. 'assunto' ou 'prazo'
    object_id    = db.Column(db.Integer,  nullable=False)
    user_id      = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    comment_text = db.Column(db.Text,     nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')  # ou backref apropriado

    def __repr__(self):
        return f'<Comment {self.id} on {self.object_type}:{self.object_id}>'
