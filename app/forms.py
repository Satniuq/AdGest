from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, SubmitField, TextAreaField, PasswordField, FloatField, SelectField, FileField
from wtforms.validators import DataRequired, Optional, Length, ValidationError, Email
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms_sqlalchemy.fields import QuerySelectMultipleField
from app.models import Client, User, Notification

def clientes_query():
    return Client.query

def usuarios_query():
    return User.query.all()

def user_clients_query():
    from flask_login import current_user
    return Client.query.filter_by(user_id=current_user.id)

#BEGIN FORM REGISTAR
class RegistrationForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(), Length(min=3, max=100)])
    nickname = StringField('Nickname', validators=[DataRequired(message="O nickname é obrigatório")])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    # Novo campo para selecionar o papel do usuário
    role = SelectField('Perfil', choices=[
        ('advogado', 'Advogado'),
        ('administrativo', 'Administrativo'),
        ('backoffice', 'Backoffice'),
        ('contabilidade', 'Contabilidade'),
        ('admin', 'Admin')
    ], validators=[DataRequired()])
    submit = SubmitField('Registrar')
#END FORM REGISTAR

#BEGIN FORM EDIT PROFILE#
class EditProfileForm(FlaskForm):
    nickname = StringField(
        'Nickname',
        validators=[
            DataRequired(message="O nickname é obrigatório"),
            Length(min=3, max=50, message="O nickname deve ter entre 3 e 50 caracteres")
        ]
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message="O email é obrigatório"),
            Email(message="Digite um email válido!")
        ]
    )
    # Campo para upload da imagem de perfil.
    profile_image = FileField('Imagem de Perfil')
    submit = SubmitField('Atualizar')
#END FORM EDIT PROFILE#

#BEGIN FORM LOGIN
class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')
#END FORM LOGIN

#BEGIN FORM ASSUNTO, TAREFA, PRAZO
class AssuntoForm(FlaskForm):
    client_existing = QuerySelectField(
        'Cliente Existente',
        query_factory=user_clients_query,  # Filtra clientes do usuário logado
        get_label='name',
        allow_blank=True,
        blank_text="-- Selecione um cliente --",
        validators=[Optional()]
    )
    client_new = StringField(
        'Novo Cliente (caso não haja existente)',
        validators=[Optional()]
    )
    nome_assunto = StringField('Assunto', validators=[DataRequired()])
    due_date = DateField('Data do Assunto', validators=[Optional()], format='%Y-%m-%d')
    sort_order = IntegerField('Ordem', validators=[Optional()])
    # Campo para seleção de usuários para partilha
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=usuarios_query,
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Salvar Assunto')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        if (not self.client_existing.data) and (not self.client_new.data or not self.client_new.data.strip()):
            msg = 'Por favor, selecione um cliente existente ou informe um novo cliente.'
            self.client_existing.errors.append(msg)
            self.client_new.errors.append(msg)
            return False
        return True

class ConcluirAssuntoForm(FlaskForm):
    horas = FloatField('Horas ao Concluir', validators=[Optional()])
    submit = SubmitField('Concluir Assunto')

class TarefaForm(FlaskForm):
    nome_tarefa = StringField('Nome da Tarefa', validators=[DataRequired()])
    descricao = StringField('Descrição (opcional)', validators=[Optional()])
    due_date = DateField('Data da Tarefa', validators=[Optional()], format='%Y-%m-%d')
    sort_order = IntegerField('Ordem', validators=[Optional()])
    horas = FloatField('Horas (opcional)', validators=[Optional()])
    
    submit = SubmitField('Salvar Tarefa')

class PrazoJudicialForm(FlaskForm):
    client_existing = QuerySelectField(
        'Cliente Existente',
        query_factory=user_clients_query,  # Filtra clientes do usuário logado
        get_label='name',
        allow_blank=True,
        blank_text="-- Selecione um cliente --",
        validators=[Optional()]
    )
    client_new = StringField(
        'Novo Cliente (caso não haja existente)',
        validators=[Optional()]
    )
    assunto = StringField('Assunto', validators=[DataRequired()])
    processo = StringField('Processo', validators=[DataRequired()])
    prazo = DateField('Prazo', validators=[Optional()], format='%Y-%m-%d')
    comentarios = TextAreaField('Comentários', validators=[Optional()])
    horas = FloatField('Horas', validators=[Optional()])
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=usuarios_query,
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Salvar Prazo')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        if not self.client_existing.data and (not self.client_new.data or not self.client_new.data.strip()):
            msg = 'Por favor, selecione um cliente existente ou informe um novo cliente.'
            self.client_existing.errors.append(msg)
            self.client_new.errors.append(msg)
            return False
        return True
#END FORM ASSUNTO, TAREFA, PRAZO

#BEGIN FORM CLIENTE
def unique_number_interno(form, field):
    if field.data:
        # Remove espaços em branco
        data = field.data.strip()
        existing = Client.query.filter(Client.number_interno == data).first()
        if existing:
            raise ValidationError('Este número interno já está em uso.')

class ClientForm(FlaskForm):
    name = StringField('Nome do Cliente', validators=[DataRequired()])
    number_interno = StringField('Número Interno', validators=[Optional()])
    nif = StringField('NIF', validators=[Optional()])
    address = StringField('Morada', validators=[Optional()])
    email = StringField('Email', validators=[Optional()])
    telephone = StringField('Telefone', validators=[Optional()])
    # NOVO: campo de partilha para clientes
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=usuarios_query,
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Salvar Cliente')
#END FORM CLIENTE

#BEGIN FORM SHARE ASSUNTO, PRAZO E CLIENTE
class ShareForm(FlaskForm):
    shared_with = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=usuarios_query,
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Atualizar Compartilhamento')
#END FORM SHARE ASSUNTO, PRAZO E CLIENTE

#BEGIN FORM COMENTÁRIO EM HISTÓRICO DE ASSUNTOS, TAREFAS, PRAZOS
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

class CommentForm(FlaskForm):
    comment_text = TextAreaField('Comentário', validators=[DataRequired()])
    submit = SubmitField('Comentar')
#END FORM COMENTÁRIO EM HISTÓRICO DE ASSUNTOS, TAREFAS, PRAZOS