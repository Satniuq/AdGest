# app/auth/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo

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

#BEGIN FORM RECUPERAR SENHA
class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Solicitar Redefinição')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirme a Senha', 
                                      validators=[DataRequired(), EqualTo('password', message='As senhas devem coincidir.')])
    submit = SubmitField('Redefinir Senha')
#END FORM RECUPERAR SENHA

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