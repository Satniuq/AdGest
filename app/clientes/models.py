from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship, backref
from app import db


class Client(db.Model):
    __tablename__ = 'clients'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)
    name = Column(String(100), nullable=False)
    number_interno = Column(String(50))
    nif = Column(String(50))
    address = Column(String(200))
    email = Column(String(100))
    telephone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relacionamento owner
    owner = relationship(
        'User',
        backref=backref('clients', lazy='dynamic'),
        foreign_keys=[user_id]
    )

    # relacionamentos auxiliares
    assuntos = relationship(
        'Assunto',
        back_populates='client',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    prazos = relationship(
        'PrazoJudicial',
        back_populates='client',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    processos = relationship(
        'Processo',
        back_populates='client',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # M:N compartilhamento de clientes
    shared_with = relationship(
        'User',
        secondary='client_shares',
        back_populates='shared_clients',
        lazy='dynamic'
    )

    # pedidos de partilha com opção
    shares = relationship(
        'ClientShare',
        back_populates='client',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_clientname'),
    )

    def __repr__(self):
        return f'<Client {self.name}>'

class ClientShare(db.Model):
    __tablename__ = 'client_shares'

    client_id = Column(Integer, ForeignKey('clients.id'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    option = Column(String(20), nullable=False, default='info')  # 'info' ou 'edit'

    client = relationship(
        'Client',
        back_populates='shares'
    )
    user = relationship(
        'User',
        back_populates='client_shares'
    )

    def __repr__(self):
        return f'<ClientShare client_id={self.client_id} user_id={self.user_id} option={self.option}>'
