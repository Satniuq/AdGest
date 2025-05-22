# app/accounting/models.py

import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    case, func, Index, UniqueConstraint,
    Numeric, Enum as SQLEnum, Column, Integer, String,
    DateTime, Date, Text, Boolean, ForeignKey, JSON
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates, relationship

from app import db
from app.clientes.models import Client
from app.billing.models import BillingNota


# --- ENUMS ------------------------------------------------------------------

class DocTipo(enum.Enum):
    FATURA  = 'fatura'
    DESPESA = 'despesa'


class StatusCobranca(enum.Enum):
    PENDENTE           = 'pendente'
    PAGA               = 'paga'
    TENTATIVA_COBRANCA = 'tentativa_cobranca'
    EM_TRIBUNAL        = 'em_tribunal'
    INCOBRAVEL         = 'incobravel'


# --- ASSOCIATION TABLE -----------------------------------------------------

billingnota_documento = db.Table(
    'billingnota_documento',
    Column('documento_id', Integer, ForeignKey('documentos_contabilisticos.id'), primary_key=True),
    Column('nota_id',      Integer, ForeignKey('billing_notas.id'),             primary_key=True),
)


# --- DOCUMENTO MODEL -------------------------------------------------------

class DocumentoContabilistico(db.Model):
    __tablename__ = 'documentos_contabilisticos'
    __table_args__ = (
        UniqueConstraint('client_id', 'tipo', 'numero', name='uq_cliente_tipo_numero'),
        Index('idx_doc_data_emissao',   'data_emissao'),
        Index('idx_doc_data_vencimento','data_vencimento'),
        Index('idx_doc_status',         'status_cobranca'),
        Index('idx_user_status',        'user_id', 'status_cobranca'),
    )

    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey('users.id'),   nullable=False)
    client_id        = Column(Integer, ForeignKey('clients.id'), nullable=False)

    numero           = Column(String(50), nullable=True)
    advogado         = Column(String(100), nullable=True)

    created_at       = Column(DateTime, default=datetime.utcnow)
    data_emissao     = Column(Date,     nullable=True)

    tipo = Column(
        SQLEnum(
            DocTipo,
            name='doc_tipo',
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls]
        ),
        nullable=False
    )

    details          = Column(Text)
    valor            = Column(Numeric(12, 2), nullable=False)
    is_confirmed     = Column(Boolean, default=False)

    status_cobranca = Column(
        SQLEnum(
            StatusCobranca,
            name='status_cobranca',
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls]
        ),
        default=StatusCobranca.PENDENTE.value
    )

    numero_recibo    = Column(String(50))
    data_vencimento  = Column(Date, nullable=True)
    numero_cliente   = Column(String(50), nullable=True)

    # Relationships
    client = relationship('Client', backref='documentos_contabilisticos')
    notas  = relationship(
        'BillingNota',
        secondary=billingnota_documento,
        backref=db.backref('documentos_contabilisticos', lazy='dynamic'),
        lazy='selectin'
    )

    # --- PROPERTIES / HYBRIDS ----------------------------------------------

    @hybrid_property
    def dias_atraso(self):
        """Dias de atraso a partir de data_vencimento ou data_emissao."""
        base = self.data_vencimento or self.data_emissao or date.today()
        delta = date.today() - base
        return max(delta.days, 0)

    @dias_atraso.expression
    def dias_atraso(cls):
        return case(
            [
                (
                    cls.data_vencimento != None,
                    func.julianday(func.current_date()) - func.julianday(cls.data_vencimento)
                ),
                (
                    cls.data_emissao  != None,
                    func.julianday(func.current_date()) - func.julianday(cls.data_emissao)
                )
            ],
            else_=0
        )

    # --- VALIDATIONS ------------------------------------------------------

    @validates('tipo')
    def validate_tipo(self, key, value):
        if isinstance(value, DocTipo):
            value = value.value
        if value not in [e.value for e in DocTipo]:
            raise ValueError("Tipo inválido")
        return value

    @validates('data_vencimento')
    def validate_data_vencimento(self, key, venc):
        if self.data_emissao and venc and venc < self.data_emissao:
            raise ValueError("Data de vencimento não pode ser anterior à data de emissão")
        return venc

    # --- REPRESENTATION & SERIALIZATION ----------------------------------

    def __repr__(self):
        return f"<DocumentoContabilistico {self.id} ({self.tipo}) Cliente:{self.client.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'client_id': self.client_id,
            'numero': self.numero,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'advogado': self.advogado,
            'data_emissao': self.data_emissao.isoformat() if self.data_emissao else None,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'tipo': self.tipo,
            'details': self.details,
            'valor': str(self.valor),
            'is_confirmed': self.is_confirmed,
            'status_cobranca': self.status_cobranca,
            'numero_recibo': self.numero_recibo,
            'numero_cliente': self.numero_cliente,
            'notas': [n.id for n in self.notas]
        }


# --- TEMPORARY DOCUMENT MODEL --------------------------------------------

class TmpDocumento(db.Model):
    __tablename__ = 'tmp_documento'

    id         = Column(Integer, primary_key=True)
    data       = Column(MutableDict.as_mutable(JSON), nullable=False)
    user_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
