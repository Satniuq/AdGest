# app/billing/forms.py

from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, SubmitField, DecimalField
from wtforms.validators import DataRequired, NumberRange
from app.accounting.models import Client

class NotaHonorariosForm(FlaskForm):
    cliente = SelectField(
        'Cliente',
        coerce=int,
        validators=[DataRequired()]
    )
    total_hours = DecimalField(
        'Total de Horas',
        places=1,
        validators=[DataRequired(), NumberRange(min=0)]
    )
    status = SelectField(
        'Status',
        choices=[('draft','Rascunho'),('pending','Pendente'),('paid','Paga')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Salvar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # popula a lista de clientes
        self.cliente.choices = [(c.id, c.name) for c in Cliente.query.order_by(Cliente.name)]

class NotaSearchForm(FlaskForm):
    source_type = SelectField(
        'Módulo',
        choices=[('', 'Todos'), ('tarefa','Tarefa'), ('prazo','Prazo')],
        default=''
    )
    date_from   = DateField('De', format='%Y-%m-%d', default=None)
    date_to     = DateField('Até', format='%Y-%m-%d', default=None)
    submit      = SubmitField('Pesquisar')

