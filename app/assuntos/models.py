#app/assuntos/models.py

from datetime import datetime
from sqlalchemy import (
    Table, Column, Integer, String, Text, DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship, backref
from app.tarefas.models import Tarefa
from app import db

# tabela many-to-many para compartilhamento de Assuntos
shared_assuntos = Table(
    'shared_assuntos',
    db.metadata,
    Column('user_id',    Integer, ForeignKey('users.id'),    primary_key=True),
    Column('assunto_id', Integer, ForeignKey('assuntos.id'), primary_key=True),
)

class Assunto(db.Model):
    __tablename__ = 'assuntos'

    id          = Column(Integer, primary_key=True)
    title       = Column(String(255), nullable=False)
    description = Column(Text)
    owner_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    client_id   = Column(Integer, ForeignKey('clients.id'), nullable=False)
    due_date    = Column(DateTime)
    sort_order  = Column(Integer, default=0)

    status       = Column(String(20), default='open')
    completed_at = Column(DateTime)
    completed_by = Column(Integer, ForeignKey('users.id'))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # dono e quem completou
    owner = relationship(
        'User',
        backref=backref('owned_assuntos', lazy='dynamic'),
        foreign_keys=[owner_id]
    )
    completer = relationship(
        'User',
        backref=backref('completed_assuntos', lazy='dynamic'),
        foreign_keys=[completed_by]
    )

    # cliente (1:N), back_populates corresponde ao Client.assuntos
    client = relationship(
        'Client',
        back_populates='assuntos',
        foreign_keys=[client_id]
    )

    # compartilhamento M:N
    shared_with = relationship(
        'User',
        secondary=shared_assuntos,
        backref=backref('shared_assuntos', lazy='dynamic'),
        lazy='dynamic'
    )

    tarefas = relationship(
        'Tarefa',
        back_populates='assunto',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    notes = relationship(
        'AssuntoNote',
        back_populates='assunto',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Assunto {self.title}>'


class AssuntoHistory(db.Model):
    __tablename__ = 'assunto_history'

    id              = Column(Integer, primary_key=True)
    assunto_id      = Column(
        Integer,
        ForeignKey('assuntos.id', ondelete='CASCADE'), 
        nullable=False
    )
    change_type     = Column(String(50), nullable=False)
    changed_at      = Column(DateTime, default=datetime.utcnow)
    changed_by      = Column(Integer, ForeignKey('users.id'), nullable=False)
    serialized_data = Column(Text, nullable=False)

    assunto = relationship(
        'Assunto',
        backref=backref(
            'history',
            lazy='dynamic',
            cascade='all, delete-orphan',
            passive_deletes=True
        ),
        foreign_keys=[assunto_id]
    )
    changer = relationship(
        'User',
        backref=backref('assunto_changes', lazy='dynamic'),
        foreign_keys=[changed_by]
    )

    def __repr__(self):
        return f'<AssuntoHistory assunto_id={self.assunto_id} type={self.change_type}>'

class AssuntoNote(db.Model):
    __tablename__ = 'assunto_notes'

    id = Column(Integer, primary_key=True)
    assunto_id = Column(Integer, ForeignKey('assuntos.id', ondelete='CASCADE'), nullable=False)
    user_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relacionamentos
    assunto = relationship(
        'Assunto',
        back_populates='notes',
        foreign_keys=[assunto_id]
    )
    user = relationship(
        'User',
        backref=backref('assunto_notes', lazy='dynamic'),
        foreign_keys=[user_id]
    )