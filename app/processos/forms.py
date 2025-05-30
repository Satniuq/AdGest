# app/processos/forms.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, DecimalField, DateField,
    SelectField, TextAreaField, SubmitField,
    HiddenField
)
from wtforms.validators import DataRequired, Optional, Length
from wtforms_sqlalchemy.fields import (
    QuerySelectField,
    QuerySelectMultipleField
)

from app.processos.models import (
    Processo,
    CaseType,
    Phase,
    PracticeArea,
    Court,
    Tag
)
from app.auth.models import User
from app.clientes.models import Client
from app import db


class DummyForm(FlaskForm):
    """Formulário vazio só para CSRF token."""
    pass

class ProcessoForm(FlaskForm):
    external_id = StringField(
        'Número Externo',
        validators=[Optional(), Length(max=100)]
    )

    case_type = QuerySelectField(
        'Tipo de Caso',
        query_factory=lambda: CaseType.query.order_by(CaseType.name).all(),
        get_label='name',
        allow_blank=True,
        blank_text='(nenhum)',
        validators=[Optional()]
    )

    phase = QuerySelectField(
        'Fase Atual',
        query_factory=lambda: [],  # será sobrescrito em __init__
        get_label='name',
        allow_blank=True,
        blank_text='(nenhuma)',
        validators=[Optional()]
    )

    practice_area = QuerySelectField(
        'Área de Prática',
        query_factory=lambda: PracticeArea.query.order_by(PracticeArea.name).all(),
        get_label='name',
        validators=[DataRequired()]
    )

    court = QuerySelectField(
        'Tribunal',
        query_factory=lambda: Court.query.order_by(Court.name).all(),
        get_label='name',
        validators=[DataRequired()]
    )

    lead_attorney = QuerySelectField(
        'Advogado Líder',
        query_factory=lambda: User.query.filter_by(role='advogado').order_by(User.nickname).all(),
        get_label='nickname',
        validators=[DataRequired()]
    )

    co_counsel = QuerySelectMultipleField(
        'Co-Advogados',
        query_factory=lambda: User.query.filter_by(role='advogado').order_by(User.nickname).all(),
        get_label='nickname',
        validators=[Optional()]
    )

    client_existing = HiddenField(
        'Cliente Existente',
        validators=[Optional()]
    )

    opposing_party = StringField(
        'Parte Adversa',
        validators=[Optional(), Length(max=255)]
    )

    value_estimate = DecimalField(
        'Valor Estimado',
        places=2,
        validators=[Optional()]
    )

    opened_at = DateField(
        'Data de Abertura',
        format='%Y-%m-%d',
        validators=[Optional()]
    )

    closed_at = DateField(
        'Data de Fechamento',
        format='%Y-%m-%d',
        validators=[Optional()]
    )

    status = SelectField(
        'Status',
        choices=[
            ('open', 'Aberto'),
            ('closed', 'Encerrado'),
            ('suspended', 'Suspenso'),
        ],
        default='open',
        validators=[DataRequired()]
    )

    tags = QuerySelectMultipleField(
        'Etiquetas',
        query_factory=lambda: Tag.query.order_by(Tag.name).all(),
        get_label='name',
        validators=[Optional()]
    )

    submit = SubmitField('Salvar Processo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Importações locais para evitar circular imports
        from app.forms.query_factories import usuarios_query
        from app.processos.services import ProcessoService

        # Atualiza dinamicamente os factories
        self.lead_attorney.query_factory = usuarios_query
        self.co_counsel.query_factory = usuarios_query

        self.case_type.query_factory = lambda: CaseType.query.order_by(CaseType.name).all()
        self.practice_area.query_factory = lambda: PracticeArea.query.order_by(PracticeArea.name).all()
        self.court.query_factory = lambda: Court.query.order_by(Court.name).all()
        self.tags.query_factory = lambda: Tag.query.order_by(Tag.name).all()

        # Ajusta fases conforme case_type selecionado
        if self.case_type.data:
            ct_id = self.case_type.data.id
            self.phase.query_factory = lambda: ProcessoService.list_phases(ct_id)
        else:
            self.phase.query_factory = lambda: []

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators)
        if not valid:
            return False

        if not self.client_existing.data:
            self.client_existing.errors.append('Selecione um cliente existente.')
            return False

        return True


class ShareProcessForm(FlaskForm):
    """Seleciona usuários com quem compartilhar este processo."""
    users = QuerySelectMultipleField(
        'Compartilhar com',
        query_factory=lambda: User.query.order_by(User.nickname).all(),
        get_label='nickname',
        validators=[Optional()]
    )
    submit = SubmitField('Atualizar Compartilhamento')

    

class ProcessNoteForm(FlaskForm):
    content = TextAreaField(
        'Nota',
        validators=[DataRequired(), Length(max=2000)],
        render_kw={
            'rows': 3,
            'placeholder': 'Escreva aqui sua nota…'
        }
    )
    submit = SubmitField('Adicionar nota')

class AddNoteForm(FlaskForm):
    content = TextAreaField(
        'Nota',
        validators=[
            DataRequired(message='O campo de nota não pode ficar vazio.'),
            Length(max=500, message='Máximo de 500 caracteres.')
        ]
    )
    submit = SubmitField('Adicionar')
