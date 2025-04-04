from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, TextAreaField, SubmitField, FileField
from wtforms.validators import DataRequired, Optional, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models import Client
from flask_login import current_user

def user_clients_query():
    # Filtra apenas os clientes do usuário logado
    return Client.query.filter_by(user_id=current_user.id)

class InvoiceForm(FlaskForm):
    client_existing = QuerySelectField(
        'Cliente Existente',
        query_factory=user_clients_query,
        get_label='name',
        allow_blank=True,
        blank_text="-- Selecione um cliente --",
        validators=[Optional()]
    )
    client_new = StringField('Novo Cliente (caso não haja existente)', validators=[Optional()])

    numero = StringField('Número', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[
        ('fatura','Fatura'), ('despesa','Despesa')
    ], validators=[DataRequired()])
    data_emissao = DateField('Data de Emissão', validators=[DataRequired()], format='%Y-%m-%d')
    valor = FloatField('Valor', validators=[DataRequired()])
    advogado = StringField('Advogado', validators=[Optional()])
    status = SelectField('Status', choices=[
        ('pendente', 'Pendente'),
        ('paga', 'Pago'),
        ('tentativa_cobranca', 'Tentativa de Cobrança'),
        ('em_tribunal', 'Em Tribunal'),
        ('incobravel', 'Incobrável')
    ], validators=[DataRequired()])
    data_vencimento = DateField('Data de Vencimento', validators=[Optional()], format='%Y-%m-%d')
    historico = TextAreaField('Histórico', validators=[Optional()])
    submit = SubmitField('Salvar')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        # Se o user não escolheu um cliente existente E não preencheu um novo
        if not self.client_existing.data and not (self.client_new.data and self.client_new.data.strip()):
            msg = 'Por favor, selecione um cliente existente ou informe um novo cliente.'
            self.client_existing.errors.append(msg)
            self.client_new.errors.append(msg)
            return False
        return True

class UploadCSVForm(FlaskForm):
    csv_file = FileField('Arquivo CSV', validators=[DataRequired()])
    submit = SubmitField('Importar')
    