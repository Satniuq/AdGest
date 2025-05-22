# app/prazos/forms.py

from flask_wtf import FlaskForm
from wtforms import DateField, StringField, TextAreaField, FloatField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, Length
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_login import current_user

from app.prazos.models import DeadlineType, RecurrenceRule
from app.processos.services import ProcessoService

class DummyForm(FlaskForm):
    """
    Formulário sem campos, apenas para gerar o CSRF token.
    """
    pass


class PrazoJudicialForm(FlaskForm):
    client          = QuerySelectField(
        'Cliente',
        query_factory=lambda: [],  # será injetado na rota
        get_label='name',
        validators=[DataRequired()]
    )
    deadline_type   = QuerySelectField(
        'Tipo de Prazo',
        query_factory=lambda: DeadlineType.query.order_by(DeadlineType.name).all(),
        get_label='name',
        validators=[DataRequired()]
    )
    recurrence_rule = QuerySelectField(
        'Recorrência',
        query_factory=lambda: RecurrenceRule.query.order_by(RecurrenceRule.name).all(),
        get_label='name',
        allow_blank=True,
        blank_text='Nenhuma',
        validators=[Optional()]
    )
    date            = DateField(
        'Data Limite',
        format='%Y-%m-%d',
        validators=[DataRequired()]
    )
    description     = StringField(
        'Descrição',
        validators=[DataRequired(), Length(max=255)]
    )
    comments        = TextAreaField(
        'Comentários',
        validators=[Optional(), Length(max=500)]
    )
    hours_spent     = FloatField(
        'Horas Gastas',
        validators=[Optional()]
    )
    status          = QuerySelectField(
        'Status',
        query_factory=lambda: [],  # injetar choices dinamicamente se precisar
        get_label=lambda x: x,
        validators=[Optional()]
    )
    submit          = SubmitField('Salvar Prazo')


class AddPrazoHoursForm(FlaskForm):
    hours       = FloatField('Horas', validators=[DataRequired()], render_kw={'step': '0.25'})
    description = StringField('Descrição', validators=[Optional(), Length(max=255)])
    ref         = HiddenField()
    submit      = SubmitField('Salvar')


class BillingForm(FlaskForm):
    hours       = FloatField('Horas', validators=[DataRequired()])
    description = StringField('Descrição', validators=[DataRequired()])
    submit      = SubmitField('Enviar ao Billing')

class PrazoNotaHonorariosForm(FlaskForm):
    submit = SubmitField('Gerar Nota de Honorários')