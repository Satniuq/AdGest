# app/accounting/forms.py

import unicodedata
from flask_wtf import FlaskForm
from wtforms import (
    StringField, FloatField, DateField, SelectField,
    TextAreaField, FileField, SubmitField, ValidationError,
    HiddenField
)
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import DataRequired, Optional
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from flask_login import current_user
from sqlalchemy import or_
from app.clientes.models import Client, ClientShare
from app.billing.models import BillingNota


def user_clients_query():
    # Retornar Query para lazy loading, não .all()
    return Client.query.filter(
        or_(
            Client.user_id == current_user.id,
            Client.shared_with.any(id=current_user.id),
            Client.shares.any(ClientShare.user_id == current_user.id)
        )
    )


class InvoiceForm(FlaskForm):
    # Campo hidden para ID do cliente (preenchido via Select2 AJAX)
    client_existing = HiddenField('Cliente Existente', validators=[DataRequired(message="Selecione um cliente existente.")])

    numero      = StringField('Número', validators=[DataRequired()])
    tipo        = SelectField('Tipo', choices=[
        ('fatura','Fatura'),
        ('despesa','Despesa')
    ], validators=[DataRequired()])
    data_emissao    = DateField('Data de Emissão', format='%Y-%m-%d', validators=[DataRequired()])
    valor           = FloatField('Valor', validators=[DataRequired()])
    advogado        = StringField('Advogado', validators=[Optional()])
    status          = SelectField('Status', choices=[
        ('pendente', 'Pendente'),
        ('paga', 'Pago'),
        ('tentativa_cobranca', 'Tentativa de Cobrança'),
        ('em_tribunal', 'Em Tribunal'),
        ('incobravel', 'Incobrável')
    ], validators=[DataRequired()])
    data_vencimento = DateField('Data de Vencimento', format='%Y-%m-%d', validators=[Optional()])
    historico       = TextAreaField('Histórico', validators=[Optional()])

    notas = QuerySelectMultipleField(
        'Notas a Faturar',
        query_factory=lambda: (
            BillingNota.query
                .join(Client)
                .filter(
                    Client.user_id == current_user.id,
                    BillingNota.status == 'pendente'
                )
                .order_by(BillingNota.created_at.desc())
        ),
        get_label=lambda n: (
            f"#{n.id} – {getattr(n.cliente, 'name', '—')} – {n.source_title} – {n.total_hours}"
        ),
        validators=[Optional()]
    )

    submit   = SubmitField('Salvar')

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if not ok:
            return False
        # Valida obrigatoriedade do cliente
        if not self.client_existing.data:
            self.client_existing.errors.append('Selecione um cliente existente.')
            return False
        return True

    def validate_data_vencimento(self, field):
        if field.data and self.data_emissao.data and field.data < self.data_emissao.data:
            raise ValidationError('A data de vencimento não pode ser anterior à data de emissão.')


class UploadCSVForm(FlaskForm):
    csv_file = FileField(
        'Arquivo CSV',
        validators=[
            FileRequired(message="Selecione um ficheiro CSV."),
            FileAllowed(['csv'], 'Só são permitidos ficheiros .csv')
        ]
    )
    submit   = SubmitField('Importar')