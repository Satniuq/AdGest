# app/assuntos/forms.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, DateField,
    IntegerField, SubmitField
)
from wtforms.validators import DataRequired, Optional, Length
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from flask_login import current_user

from app.forms.query_factories import user_clients_query, usuarios_query
from app.assuntos.services import AssuntoService

class AssuntoForm(FlaskForm):
    client_existing = QuerySelectField(
        'Cliente Existente',
        query_factory=user_clients_query,
        get_label='name',
        allow_blank=True,
        blank_text="-- Selecione um cliente --",
        validators=[Optional()]
    )
    client_new = StringField(
        'Novo Cliente (caso não haja existente)',
        validators=[Optional(), Length(max=100)]
    )
    title = StringField(
        'Título do Assunto',
        validators=[DataRequired(), Length(max=100)]
    )
    description = TextAreaField(
        'Descrição',
        validators=[Optional(), Length(max=1000)],
        render_kw={'rows': 3}
    )
    due_date = DateField(
        'Data do Assunto',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    sort_order = IntegerField(
        'Ordem',
        validators=[Optional()]
    )
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=lambda: AssuntoService.available_users(current_user.id),
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Salvar Assunto')

    def validate(self, extra_validators=None):
        # validamos que veio um cliente ou um nome de novo cliente
        if not super().validate(extra_validators):
            return False
        if (not self.client_existing.data
            and not (self.client_new.data and self.client_new.data.strip())):
            msg = 'Selecione um cliente existente ou informe um nome de cliente.'
            self.client_existing.errors.append(msg)
            self.client_new.errors.append(msg)
            return False
        return True

class ShareAssuntoForm(FlaskForm):
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=lambda: AssuntoService.available_users(current_user.id),
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Compartilhar Assunto')

class NoteForm(FlaskForm):
    content = TextAreaField('Nota', validators=[DataRequired()])
    submit  = SubmitField('Salvar Nota')

class DummyForm(FlaskForm):
    """Formulário vazio só para CSRF token."""
    pass