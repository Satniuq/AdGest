# app/tarefas/forms.py

from datetime import datetime, date
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField,
    IntegerField, FloatField, HiddenField, SubmitField
)
# Para WTForms ≥3 use de wtforms.fields; se der erro, cai no html5
try:
    from wtforms.fields import DateField
except ImportError:
    from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, ValidationError, NumberRange, Optional
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField

class TarefaForm(FlaskForm):
    title             = StringField(
        'Título',
        validators=[DataRequired(), Length(max=255)]
    )
    description       = TextAreaField(
        'Descrição',
        validators=[Optional(), Length(max=200)]
    )
    due_date          = DateField(
        'Data de Vencimento',
        format='%Y-%m-%d',
        validators=[DataRequired()],
        render_kw={'type': 'date'}
    )
    status            = SelectField(
        'Status',
        choices=[('open','Aberto'), ('done','Concluído')],
        default='open'
    )
    sort_order        = IntegerField(
        'Ordem',
        validators=[Optional()]
    )
    hours_estimate    = FloatField(
        'Horas Estimadas (opcional)',
        validators=[Optional()]
    )
    reminder_offset   = IntegerField(
        'Lembrar (minutos antes)',
        validators=[NumberRange(min=0)],
        default=0
    )
    # stub para não quebrar templates que esperam recurrence_rule
    recurrence_rule   = HiddenField()

    shared_with       = QuerySelectMultipleField(
        'Compartilhar com',
        get_label='username',
        allow_blank=True
    )
    calendar_event_id = HiddenField()
    notified_at       = HiddenField()

    submit = SubmitField('Salvar')

    def __init__(self, *args, **kwargs):
        # para edição: recebe obj=Tarefa
        self.obj = kwargs.get('obj', None)
        super().__init__(*args, **kwargs)

        # popula o select de compartilhamento
        from app.tarefas.services import TarefaService
        self.shared_with.query_factory = lambda: TarefaService.available_users(current_user.id)

        # se for edição, pré-preenche status
        if self.obj:
            self.status.data = self.obj.status

    def validate_due_date(self, field):
        if field.data < date.today():
            raise ValidationError('A data de vencimento deve ser hoje ou no futuro.')

    def validate_title(self, field):
        from app.tarefas.services import TarefaService

        # obtém o assunto_id: se for edição, a partir de self.obj; se for criação, espera-se que
        # você passe 'assunto_id' como hidden field ou trate no serviço
        assunto_id = getattr(self.obj, 'assunto_id', None)

        exists = TarefaService.find_by_title(
            title=field.data,
            user_id=current_user.id,
            assunto_id=assunto_id
        )
        if exists and (not self.obj or exists.id != self.obj.id):
            raise ValidationError('Já existe uma tarefa com este título neste assunto.')

class NoteForm(FlaskForm):
    content = TextAreaField('Nota', validators=[DataRequired()])
    submit  = SubmitField('Salvar Nota')

class BillingForm(FlaskForm):
    history_id  = HiddenField(validators=[DataRequired()])
    hours       = FloatField('Horas', validators=[DataRequired()])
    description = StringField('Descrição', validators=[DataRequired()])
    submit      = SubmitField('Enviar ao Billing')

class NotaHonorariosForm(FlaskForm):
    submit = SubmitField('Gerar Nota de Honorários')

class ConcluirTarefaForm(FlaskForm):
    horas  = FloatField(
        'Horas ao Concluir',
        validators=[Optional()]
    )
    submit = SubmitField('Concluir Tarefa')

class AddHoursForm(FlaskForm):
    horas       = FloatField(
        'Horas',
        validators=[DataRequired()],
        render_kw={'step': '0.25'}
    )
    description = StringField(
        'Descrição',
        validators=[Optional(), Length(max=255)]
    )
    ref         = HiddenField()
    submit      = SubmitField('Salvar')

class DummyForm(FlaskForm):
    """Formulário vazio só para CSRF token."""
    pass