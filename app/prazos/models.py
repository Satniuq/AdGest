# app/prazos/models.py

from datetime import datetime
from sqlalchemy import Interval, Table, Column, Integer, ForeignKey, Date, String, Text, Float, DateTime, JSON
from sqlalchemy.orm import relationship, backref
from app import db
from app.billing.models import BillingNota

# tabela de associação para compartilhamento de prazos
shared_prazos = Table(
    'shared_prazos',
    db.metadata,
    Column('user_id',  Integer, ForeignKey('users.id'),   primary_key=True),
    Column('prazo_id', Integer, ForeignKey('prazos.id'),  primary_key=True),
)

class DeadlineType(db.Model):
    __tablename__ = 'deadline_types'
    id          = Column(Integer, primary_key=True)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))

class RecurrenceRule(db.Model):
    __tablename__ = 'recurrence_rules'
    id    = Column(Integer, primary_key=True)
    name  = Column(String(100), unique=True, nullable=False)
    rrule = Column(String(255), nullable=False)

class PrazoJudicial(db.Model):
    __tablename__ = 'prazos'
    id               = Column(Integer, primary_key=True)
    processo_id      = Column(Integer, ForeignKey('processos.id'), nullable=False)
    owner_id         = Column(Integer, ForeignKey('users.id'),     nullable=False)
    client_id        = Column(Integer, ForeignKey('clients.id'),   nullable=False)
    type_id          = Column(Integer, ForeignKey('deadline_types.id'),   nullable=False)
    recur_rule_id    = Column(Integer, ForeignKey('recurrence_rules.id'))
    date             = Column(Date,   nullable=False)
    description      = Column(String(255), nullable=False)
    comments         = Column(Text)
    hours_spent      = Column(Float, default=0.0)
    notified_at      = Column(DateTime)
    reminder_offset  = Column(Interval)
    calendar_event_id= Column(String(255))
    status           = Column(String(50), default='open')
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relacionamento com Processo (1:N)
    processo    = relationship('Processo', back_populates='prazos')

    # relacionamento com o usuário que criou este prazo (1:N)
    owner       = relationship('User', back_populates='created_prazos')

    # relacionamento com o cliente (1:N)
    client      = relationship('Client', back_populates='prazos')

    # relacionamento com tipo e regra de recorrência (1:N)
    type        = relationship('DeadlineType',   backref=backref('prazos', lazy='dynamic'))
    recurrence  = relationship('RecurrenceRule', backref=backref('prazos', lazy='dynamic'))

    # histórico de alterações (1:N)
    history     = relationship(
        'PrazoHistory',
        back_populates='prazo',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    billing_items = relationship(
        'PrazoBillingItem',
        back_populates='prazo',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    notas_honorarios = relationship(
        'PrazoNotaHonorarios',
        back_populates='prazo',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='desc(PrazoNotaHonorarios.created_at)'
    )

    # compartilhamento many-to-many com outros usuários
    shared_with = relationship(
        'User',
        secondary=shared_prazos,
        backref=backref('shared_prazos', lazy='dynamic'),
        lazy='dynamic'
    )

class PrazoHistory(db.Model):
    __tablename__ = 'prazo_history'
    id         = Column(Integer, primary_key=True)
    prazo_id   = Column(Integer, ForeignKey('prazos.id'), nullable=False)
    change_type= Column(String(50), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(Integer, ForeignKey('users.id'))
    snapshot   = Column(JSON)
    detail     = Column(String(255))

    # relacionamento de volta ao prazo
    prazo = relationship('PrazoJudicial', back_populates='history')

    # usuário que fez a alteração
    changed_by_user = relationship(
        'User',
        backref=backref('prazo_changes', lazy='dynamic')
    )

class PrazoBillingItem(db.Model):
    __tablename__ = 'prazo_billing_items'

    id                  = Column(Integer, primary_key=True)
    prazo_id            = Column(Integer, ForeignKey('prazos.id'), nullable=False)
    history_id          = Column(Integer, ForeignKey('prazo_history.id'), nullable=False)
    hours               = Column(Float, nullable=False)
    description         = Column(String(255))
    created_by          = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow)
    external_billing_id = Column(String(255))

    invoiced            = Column(db.Boolean, default=False, nullable=False)
    


    prazo    = relationship('PrazoJudicial', back_populates='billing_items')
    history  = relationship('PrazoHistory')
    user     = relationship('User')

class PrazoNotaHonorarios(db.Model):
    __tablename__ = 'prazo_nota_honorarios'
    id          = db.Column(db.Integer, primary_key=True)
    prazo_id    = db.Column(db.Integer, db.ForeignKey('prazos.id', ondelete='CASCADE'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_hours = db.Column(db.Float, nullable=False)

    prazo   = relationship('PrazoJudicial', back_populates='notas_honorarios')
    items   = relationship('PrazoNotaHonorariosItem',
                           back_populates='nota',
                           cascade='all, delete-orphan',
                           passive_deletes=True)
    creator = relationship('User')

    @property
    def billing(self):
        """Retorna a BillingNota global associada (source_type='prazo')."""
        return BillingNota.query.filter_by(
            source_type='prazo',
            source_id=self.id
        ).first()

class PrazoNotaHonorariosItem(db.Model):
    __tablename__ = 'prazo_nota_honorarios_item'
    id          = db.Column(db.Integer, primary_key=True)
    nota_id     = db.Column(db.Integer, db.ForeignKey('prazo_nota_honorarios.id', ondelete='CASCADE'), nullable=False)
    history_id  = db.Column(db.Integer, nullable=False)
    date        = db.Column(db.DateTime, nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    hours       = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255))

    nota = db.relationship('PrazoNotaHonorarios', back_populates='items')
    user = db.relationship('User')
