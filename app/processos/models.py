#app/processos/models.py
from datetime import datetime
from sqlalchemy import (
    Table, Column, Integer, String, DateTime, ForeignKey,
    Numeric, Text, JSON
)
from sqlalchemy.orm import relationship, backref
from app import db

# associações many-to-many
shared_processes = Table(
    'shared_processes',
    db.metadata,
    Column('user_id',    Integer, ForeignKey('users.id'),    primary_key=True),
    Column('process_id', Integer, ForeignKey('processos.id'), primary_key=True),
)
process_co_counsel = Table(
    'process_co_counsel',
    db.metadata,
    Column('process_id',  Integer, ForeignKey('processos.id'), primary_key=True),
    Column('attorney_id', Integer, ForeignKey('users.id'),      primary_key=True),
)
process_tags = Table(
    'process_tags',
    db.metadata,
    Column('process_id', Integer, ForeignKey('processos.id'), primary_key=True),
    Column('tag_id',     Integer, ForeignKey('tags.id'),       primary_key=True),
)

class PracticeArea(db.Model):
    __tablename__ = 'practice_areas'
    id          = Column(Integer, primary_key=True)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(Text)

class Court(db.Model):
    __tablename__ = 'courts'
    id        = Column(Integer, primary_key=True)
    name      = Column(String(150), unique=True, nullable=False)
    address   = Column(String(255))

class CaseType(db.Model):
    __tablename__ = 'case_types'
    id    = Column(Integer, primary_key=True)
    name  = Column(String(100), unique=True, nullable=False)

    # fases específicas deste tipo de caso
    phases = relationship(
        'Phase',
        back_populates='case_type',
        lazy='dynamic',
        order_by='Phase.sort_order',
        cascade='all, delete-orphan'
    )

class Phase(db.Model):
    __tablename__ = 'phases'
    id           = Column(Integer, primary_key=True)
    case_type_id = Column(Integer, ForeignKey('case_types.id'), nullable=False)
    name         = Column(String(100), nullable=False)
    sort_order   = Column(Integer, default=0)
    description  = Column(Text)

    case_type = relationship('CaseType', back_populates='phases')

class Processo(db.Model):
    __tablename__ = 'processos'
    id               = Column(Integer, primary_key=True)
    external_id      = Column(String(100), unique=True)
    case_type_id     = Column(Integer, ForeignKey('case_types.id'))
    phase_id         = Column(Integer, ForeignKey('phases.id'), nullable=True)
    practice_area_id = Column(Integer, ForeignKey('practice_areas.id'), nullable=False)
    court_id         = Column(Integer, ForeignKey('courts.id'),         nullable=False)
    lead_attorney_id = Column(Integer, ForeignKey('users.id'),          nullable=False)
    client_id        = Column(Integer, ForeignKey('clients.id'),        nullable=False)
    status           = Column(String(50), default='open', nullable=False)
    opposing_party   = Column(String(255))
    value_estimate   = Column(Numeric(12, 2))
    opened_at        = Column(DateTime, default=datetime.utcnow)
    closed_at        = Column(DateTime)
    __table_args__   = (db.Index('ix_processos_ext', 'external_id'),)

    # relacionamentos
    case_type      = relationship('CaseType',     backref=backref('processos', lazy='dynamic'))
    phase          = relationship('Phase')   # fase atual
    practice_area  = relationship('PracticeArea', backref='processos')
    court          = relationship('Court',         backref='processos')
    lead_attorney  = relationship('User', back_populates='led_processes')
    client         = relationship('Client', back_populates='processos')
    prazos         = relationship('PrazoJudicial', back_populates='processo', cascade='all, delete-orphan')
    shared_with    = relationship('User', secondary=shared_processes, backref='shared_processes', lazy='dynamic')
    co_counsel     = relationship('User', secondary=process_co_counsel, backref='co_counseled_processes', lazy='dynamic')
    tags           = relationship('Tag', secondary=process_tags, backref='processos', lazy='dynamic')

class Tag(db.Model):
    __tablename__ = 'tags'
    id   = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

class Hearing(db.Model):
    __tablename__ = 'hearings'
    id          = Column(Integer, primary_key=True)
    processo_id = Column(Integer, ForeignKey('processos.id'), nullable=False)
    when        = Column(DateTime, nullable=False)
    type        = Column(String(100))
    judge       = Column(String(100))
    location    = Column(String(255))

    processo = relationship('Processo', backref=backref('hearings', lazy='dynamic'))

class Document(db.Model):
    __tablename__ = 'documents'
    id           = Column(Integer, primary_key=True)
    processo_id  = Column(Integer, ForeignKey('processos.id'), nullable=False)
    filename     = Column(String(255))
    uploaded_at  = Column(DateTime, default=datetime.utcnow)

    processo = relationship('Processo', backref=backref('documents', lazy='dynamic'))

class ProcessNote(db.Model):
    __tablename__ = 'process_notes'
    id           = Column(Integer, primary_key=True)
    processo_id  = Column(Integer, ForeignKey('processos.id'), nullable=False)
    created_by   = Column(Integer, ForeignKey('users.id'), nullable=False)
    content      = Column(Text, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    processo = relationship('Processo', backref=backref('notes', lazy='dynamic'))
    author   = relationship('User',      backref=backref('process_notes', lazy='dynamic'))

class ProcessoHistory(db.Model):
    __tablename__ = 'processo_history'

    id           = Column(Integer, primary_key=True)
    processo_id  = Column(Integer, ForeignKey('processos.id'), nullable=False)
    change_type  = Column(String(50), nullable=False)
    changed_at   = Column(DateTime, default=datetime.utcnow)
    changed_by   = Column(Integer, ForeignKey('users.id'))
    snapshot     = Column(JSON)

    # relacionamento de volta ao processo
    processo = relationship(
        'Processo',
        backref=backref('history', lazy='dynamic', cascade='all, delete-orphan')
    )

    # usuário que fez a alteração
    changed_by_user = relationship(
        'User',
        backref=backref('process_changes', lazy='dynamic')
    )
