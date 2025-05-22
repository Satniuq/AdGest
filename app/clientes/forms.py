# app/clientes/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError, BooleanField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Optional
from wtforms_sqlalchemy.fields import QuerySelectMultipleField

from app.clientes.models import Client

def unique_number_interno(form, field):
    """Valida unicidade de número interno."""
    if field.data:
        data = field.data.strip()
        existing = Client.query.filter(Client.number_interno == data).first()
        if existing and (not hasattr(form, 'obj') or existing.id != getattr(form.obj, 'id', None)):
            raise ValidationError('Este número interno já está em uso.')

class ClientForm(FlaskForm):
    name = StringField('Nome do Cliente', validators=[DataRequired()])
    number_interno = StringField('Número Interno', validators=[Optional(), unique_number_interno])
    nif = StringField('NIF', validators=[Optional()])
    address = StringField('Morada', validators=[Optional()])
    email = StringField('Email', validators=[Optional()])
    telephone = StringField('Telefone', validators=[Optional()])

    # não atribuir query_factory aqui:
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        get_label='nickname',
        validators=[Optional()]
    )

    submit = SubmitField('Salvar Cliente')

    def __init__(self, *args, **kwargs):
        # opcional: para editar, poder comparar no unique_number_interno
        self.obj = kwargs.get('obj', None)
        super().__init__(*args, **kwargs)
        # só aqui importamos para evitar ciclo
        from app.forms.query_factories import usuarios_query
        self.shared_with.query_factory = usuarios_query


class ShareForm(FlaskForm):
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Atualizar Compartilhamento')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.forms.query_factories import usuarios_query
        self.shared_with.query_factory = usuarios_query

class UploadCSVForm(FlaskForm):
    csv_file = FileField(
        'Ficheiro CSV',
        validators=[ FileAllowed(['csv'], 'Só .csv permitido') ]
    )
    submit   = SubmitField('Carregar CSV')