# app/tarefas/models.py

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    ForeignKey, Float, Table, and_
)
from sqlalchemy.orm import relationship, backref, foreign
from app import db
from app.models_main import HoraAdicao
from app.billing.models import BillingNota

# tabela many-to-many para compartilhamento de tarefas
shared_tarefas = Table(
    'shared_tarefas',
    db.metadata,
    Column('user_id',   Integer, ForeignKey('users.id'),   primary_key=True),
    Column('tarefa_id', Integer, ForeignKey('tarefas.id'), primary_key=True),
)

class TarefaNote(db.Model):
    __tablename__ = 'tarefa_notes'

    id         = Column(Integer, primary_key=True)
    tarefa_id  = Column(Integer, ForeignKey('tarefas.id', ondelete='CASCADE'), nullable=False)
    user_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relacionamentos
    tarefa = relationship(
        'Tarefa',
        back_populates='notes',
        foreign_keys=[tarefa_id]
    )
    user = relationship(
        'User',
        backref=backref('tarefa_notes', lazy='dynamic'),
        foreign_keys=[user_id]
    )

class TarefaBillingItem(db.Model):
    __tablename__ = 'tarefa_billing_items'
    id          = Column(Integer, primary_key=True)
    tarefa_id   = Column(Integer, ForeignKey('tarefas.id'), nullable=False)
    history_id  = Column(Integer, ForeignKey('tarefas_history.id'), nullable=False)
    hours       = Column(Float, nullable=False)
    description = Column(String(255))
    created_by  = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    invoiced    = db.Column(db.Boolean, default=False, nullable=False)

    tarefa  = relationship('Tarefa',        back_populates='billing_items')
    history = relationship('TarefaHistory')
    user    = relationship('User')

class Tarefa(db.Model):
    __tablename__ = 'tarefas'

    id                = Column(Integer, primary_key=True)
    title             = Column(String(255), nullable=False)
    description       = Column(Text)
    owner_id          = Column(Integer, ForeignKey('users.id'), nullable=False)
    assunto_id        = Column(Integer, ForeignKey('assuntos.id'), nullable=False)
    due_date          = Column(DateTime)
    sort_order        = Column(Integer, default=0)
    hours_estimate    = Column(Float)
    status            = Column(String(20), default='open')
    reminder_offset   = Column(Integer, default=0)
    calendar_event_id = Column(String(255))
    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship(
        'User',
        backref=backref('owned_tarefas', lazy='dynamic'),
        foreign_keys=[owner_id]
    )

    assunto = relationship(
        'Assunto',
        back_populates='tarefas',
        foreign_keys=[assunto_id]
    )

    shared_with = relationship(
        'User',
        secondary=shared_tarefas,
        backref=backref('shared_tarefas', lazy='dynamic'),
        lazy='dynamic'
    )

    history = relationship(
        'TarefaHistory',
        back_populates='tarefa',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    additions = relationship(
        HoraAdicao,
        primaryjoin=and_(
            foreign(HoraAdicao.item_id) == id,
            HoraAdicao.item_type == 'tarefa'
        ),
        foreign_keys=[HoraAdicao.item_id],
        backref=backref('tarefa', lazy='joined'),
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    notes = relationship(
        'TarefaNote',
        back_populates='tarefa',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    billing_items = relationship(
        'TarefaBillingItem',
        back_populates='tarefa',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    history = relationship(
        'TarefaHistory', back_populates='tarefa',
        cascade='all, delete-orphan', lazy='dynamic'
    )

    notas_honorarios = db.relationship(
        'NotaHonorarios',
        back_populates='tarefa',
        order_by='desc(NotaHonorarios.created_at)'
    )

    def __repr__(self):
        return f'<Tarefa {self.title}>'


class TarefaHistory(db.Model):
    __tablename__ = 'tarefas_history'

    id              = Column(Integer, primary_key=True)
    tarefa_id       = Column(Integer, ForeignKey('tarefas.id'), nullable=False)
    tarefa          = relationship('Tarefa', back_populates='history')

    serialized_data = Column(Text, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)

    change_type     = Column(String(50), nullable=False)   # ex: 'created', 'updated', 'hours_added'
    changed_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    changed_by      = Column(Integer, ForeignKey('users.id'), nullable=False)

    user_id         = Column(Integer, ForeignKey('users.id'), nullable=False)
    user            = relationship('User', foreign_keys=[user_id])
    detail          = Column(String(100))

    def __repr__(self):
        return f'<TarefaHistory tarefa_id={self.tarefa_id}>'

class NotaHonorarios(db.Model):
    __tablename__ = 'nota_honorarios'
    id = db.Column(db.Integer, primary_key=True)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefas.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_hours = db.Column(db.Float, nullable=False)

    # relações
    tarefa = db.relationship('Tarefa', back_populates='notas_honorarios')
    items = db.relationship('NotaHonorariosItem', back_populates='nota', cascade='all, delete-orphan')
    creator = db.relationship('User')  # ajusta se o teu User tiver outro nome

    @property
    def billing(self):
        """Retorna a BillingNota associada a esta NotaHonorarios."""
        return BillingNota.query.filter_by(
            source_type='tarefa',
            source_id=self.id
        ).first()

class NotaHonorariosItem(db.Model):
    __tablename__ = 'nota_honorarios_item'
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey('nota_honorarios.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    hours = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255))

    # relações
    nota = db.relationship('NotaHonorarios', back_populates='items')
    user = db.relationship('User')

    @property
    def billing(self):
        """Retorna a BillingNota global associada (source_type='tarefa')."""
        return BillingNota.query.filter_by(
            source_type='tarefa',
            source_id=self.id
        ).first()