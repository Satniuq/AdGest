# app/billing/models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app import db
from app.clientes.models import Client

class BillingNota(db.Model):
    __tablename__ = 'billing_notas'
    id           = Column(Integer, primary_key=True)
    source_type  = Column(Enum('tarefa','prazo', name='billing_source'), nullable=False)
    source_id    = Column(Integer, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by   = Column(Integer, ForeignKey('users.id'), nullable=False)
    total_hours  = Column(Float, nullable=False)

    status       = Column(String(20), nullable=False, default='pendente')

    cliente_id   = Column(Integer, ForeignKey('clients.id'), nullable=False)
    cliente      = relationship('Client', backref='billing_notas')

    creator      = relationship('User', foreign_keys=[created_by])
    items        = relationship('BillingNotaItem', back_populates='nota', cascade='all, delete-orphan')

    @property
    def source_obj(self):
        """Devolve o objeto Tarefa ou PrazoJudicial associado."""
        if self.source_type == 'tarefa':
            from app.tarefas.models import Tarefa
            return Tarefa.query.get(self.source_id)
        elif self.source_type == 'prazo':
            from app.prazos.models import PrazoJudicial
            return PrazoJudicial.query.get(self.source_id)
        return None

    @property
    def source_title(self):
        """Título legível: .title (Tarefa) ou .description (PrazoJudicial)."""
        obj = self.source_obj
        if not obj:
            return ''
        # Tarefa tem .title; PrazoJudicial tem .description
        return getattr(obj, 'title', getattr(obj, 'description', ''))

class BillingNotaItem(db.Model):
    __tablename__ = 'billing_nota_items'
    id           = Column(Integer, primary_key=True)
    nota_id      = Column(Integer, ForeignKey('billing_notas.id'), nullable=False)
    date         = Column(DateTime, nullable=False)
    user_id      = Column(Integer, ForeignKey('users.id'), nullable=False)
    hours        = Column(Float, nullable=False)
    description  = Column(String(255))

    nota         = relationship('BillingNota', back_populates='items')
    user         = relationship('User')
