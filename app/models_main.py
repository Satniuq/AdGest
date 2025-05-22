# app/models_main.py

import json
from . import db
from flask_login import UserMixin
from datetime import datetime, date
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app


class HourEntry(db.Model):
    __tablename__ = 'hour_entries'
    id = db.Column(db.Integer, primary_key=True)
    object_type = db.Column(db.String(20), nullable=False)  # 'tarefa' ou 'prazo'
    object_id = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<HourEntry {self.object_type}:{self.object_id} - {self.hours}h em {self.entry_date}>'

class HoraAdicao(db.Model):
    __tablename__ = 'horas_adicao'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20), nullable=False)  # 'assunto', 'tarefa' ou 'prazo'
    item_id = db.Column(db.Integer, nullable=False)
    horas_adicionadas = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    