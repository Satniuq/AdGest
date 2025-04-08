import json

from . import db
from flask_login import UserMixin
from datetime import datetime, date

#BEGIN MODEL TABELA ASSOCIAÇÃO ASSUNTOS, PRAZOS E CLIENTES
# Tabela de associação para assuntos, prazos e clientes
shared_assuntos = db.Table('shared_assuntos',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('assunto_id', db.Integer, db.ForeignKey('assuntos.id'))
)

shared_prazos = db.Table('shared_prazos',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('prazo_id', db.Integer, db.ForeignKey('prazos_judiciais.id'))
)

shared_clients = db.Table('shared_clients',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('client_id', db.Integer, db.ForeignKey('clients.id'))
)
#END MODEL TABELA ASSOCIAÇÃO ASSUNTOS, PRAZOS E CLIENTES

#BEGIN MODEL USER
# Usuário
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    nickname = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_image = db.Column(db.String(120), default='default.jpg')
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='advogado')

    __table_args__ = (db.UniqueConstraint('email', name='uq_users_email'),)

    # relacionamentos:
    assuntos_compartilhados = db.relationship(
        'Assunto',
        secondary=shared_assuntos,
        backref=db.backref('compartilhados', lazy='dynamic'),
        lazy='dynamic'
    )
    
    # Relação reversa para as associações de clientes compartilhados
    client_shares = db.relationship('ClientShare', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'

#END MODEL USER

#BEGIN MODEL AUDITORIA
# Log de Auditoria
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_id} at {self.timestamp}>'
#END MODEL AUDITORIA

#BEGIN MODEL ASSUNTO
class Assunto(db.Model):
    __tablename__ = 'assuntos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Dono
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    nome_assunto = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    horas_assunto = db.Column(db.Float, default=0.0)
    is_completed = db.Column(db.Boolean, default=False)
    is_billed = db.Column(db.Boolean, default=False)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    tarefas = db.relationship('Tarefa', backref='assunto', cascade="all, delete-orphan", lazy='dynamic')
    shared_with = db.relationship(
        'User',
        secondary=shared_assuntos,
        backref=db.backref('shared_assuntos', lazy='dynamic', overlaps="assuntos_compartilhados,compartilhados"),
        lazy='dynamic',
        overlaps="assuntos_compartilhados,compartilhados"
    )

    # RELACIONAMENTO PARA ACESSAR O DONO – certifique-se de que ESTÁ indentado dentro da classe
    user = db.relationship("User", backref="assuntos_criados", foreign_keys=lambda: [Assunto.__table__.c.user_id])

    def __repr__(self):
        return f'<Assunto {self.client.name} - {self.nome_assunto}>'
#END MODEL ASSUNTO

#BEGIN MODEL TAREFA
class Tarefa(db.Model):
    __tablename__ = 'tarefas'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assunto_id = db.Column(db.Integer, db.ForeignKey('assuntos.id'), nullable=False)
    nome_tarefa = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)
    horas = db.Column(db.Float, default=0.0)
    is_billed = db.Column(db.Boolean, default=False)
    data_conclusao = db.Column(db.Date, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    user = db.relationship("User", backref="tarefas_criadas", foreign_keys=lambda: [Tarefa.__table__.c.user_id])

    def __repr__(self):
        return f'<Tarefa {self.nome_tarefa} (Assunto: {self.assunto.nome_assunto if self.assunto else "N/A"})>'

#END MODEL TAREFA

#BEGIN MODEL PRAZO
class PrazoJudicial(db.Model):
    __tablename__ = 'prazos_judiciais'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    assunto = db.Column(db.String(100), nullable=False)
    processo = db.Column(db.String(100), nullable=False)
    prazo = db.Column(db.Date, nullable=True)
    comentarios = db.Column(db.Text, nullable=True)
    status = db.Column(db.Boolean, default=False)
    horas = db.Column(db.Float, default=0.0)
    is_billed = db.Column(db.Boolean, default=False)
    data_conclusao = db.Column(db.Date, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    client = db.relationship('Client', backref='prazos_judiciais')
    
    shared_with = db.relationship(
        'User',
        secondary=shared_prazos,
        backref=db.backref('shared_prazos', lazy='dynamic', overlaps="prazos_compartilhados,compartilhados"),
        lazy='dynamic',
        overlaps="prazos_compartilhados,compartilhados"
    )

    user = db.relationship("User", backref="prazos_criados", foreign_keys=lambda: [PrazoJudicial.__table__.c.user_id])

    def __repr__(self):
        return f'<PrazoJudicial {self.client.name} - {self.assunto}>'
#END MODEL PRAZO

#BEGIN MODEL HOUR ENTRY - TAREFAS, PRAZOS
# Hour Entry
class HourEntry(db.Model):
    __tablename__ = 'hour_entries'
    id = db.Column(db.Integer, primary_key=True)
    object_type = db.Column(db.String(20), nullable=False)  # 'tarefa' ou 'prazo'
    object_id = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<HourEntry {self.object_type}:{self.object_id} - {self.hours}h em {self.entry_date}>'
#END MODEL HOUR ENTRY - TAREFAS, PRAZOS

#BEGIN MODEL HISTÓRICO DE CARDS DE ASSUNTOS, TAREFAS, PRAZOS
class AssuntoHistory(db.Model):
    __tablename__ = 'assuntos_history'
    id = db.Column(db.Integer, primary_key=True)
    assunto_id = db.Column(db.Integer, nullable=False)  # FK para o assunto original
    change_type = db.Column(db.String(20))  # 'created', 'updated', 'deleted'
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Armazene as mudanças – pode ser um JSON com um snapshot ou somente os campos alterados
    snapshot = db.Column(db.JSON)  # Requer que seu banco suporte JSON

    def __repr__(self):
        return f"<Histórico Assunto {self.assunto_id} {self.change_type} em {self.changed_at}>"

class TarefaHistory(db.Model):
    __tablename__ = 'tarefas_history'
    id = db.Column(db.Integer, primary_key=True)
    tarefa_id = db.Column(db.Integer, nullable=False)  # FK para a tarefa
    change_type = db.Column(db.String(20), nullable=False)  # ex.: 'created', 'edited'
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    snapshot = db.Column(db.JSON)  # ou db.Column(db.Text)

    def __repr__(self):
        return f"<TarefaHistory {self.tarefa_id} {self.change_type} em {self.changed_at}>"

class PrazoHistory(db.Model):
    __tablename__ = 'prazos_history'
    id = db.Column(db.Integer, primary_key=True)
    prazo_id = db.Column(db.Integer, nullable=False)  # FK para o prazo original
    change_type = db.Column(db.String(20))  # 'criado', 'editado', 'excluído', etc.
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    snapshot = db.Column(db.JSON)  # Armazene as mudanças como JSON

    def __repr__(self):
        return f"<PrazoHistory {self.prazo_id} {self.change_type} em {self.changed_at}>"

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    object_type = db.Column(db.String(50))  # 'assunto', 'tarefa' ou 'prazo'
    object_id = db.Column(db.Integer, nullable=False)  # ID do assunto/tarefa/prazo
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='comments')

    def __repr__(self):
        return f"<Comment {self.id} em {self.object_type}:{self.object_id}>"
#END MODEL HISTÓRICO DE CARDS DE ASSUNTOS, TAREFAS, PRAZOS

#BEGIN MODEL CLIENTE
class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # unique=True removido
    number_interno = db.Column(db.String(50), nullable=True)
    nif = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    telephone = db.Column(db.String(20), nullable=True)
    
    assuntos = db.relationship('Assunto', backref='client', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_user_clientname'),
    )
    
    # Relacionamento para partilha de clientes
    shares = db.relationship('ClientShare', backref='client', lazy='dynamic')
    
    def __repr__(self):
        return f'<Client {self.name}>'
#END MODEL CLIENTE

#BEGIN MODEL SHARE CLIENTE
#  modelo de associação de partilha de clientes
class ClientShare(db.Model):
    __tablename__ = 'client_shares'
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    option = db.Column(db.String(50), nullable=False)  # Armazena "info", "historico" ou "billing"

    def __repr__(self):
        return f'<ClientShare client_id:{self.client_id} user_id:{self.user_id} option:{self.option}>'
#END MODEL SHARE CLIENTE

#BEGIN MODEL NOTA DE HONORÁRIOS
class NotaHonorarios(db.Model):
    __tablename__ = 'nota_honorarios'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)  # Lista de itens faturados (por exemplo, "Tarefa 5, Prazo 3")
    total_hours = db.Column(db.Float, default=0.0)
    is_confirmed = db.Column(db.Boolean, default=False)  # Pode ser usado para indicar se a nota já foi finalizada

    client = db.relationship('Client', backref='nota_honorarios')
    
    def __repr__(self):
        return f'<NotaHonorarios {self.id} - Client: {self.client.name}>'
#END MODEL NOTA DE HONORÁRIOS

#BEGIN MODEL DOCUMENTO CONTABILIDADE
class DocumentoContabilistico(db.Model):
    __tablename__ = 'documentos_contabilisticos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    numero = db.Column(db.String(50), nullable=True)
    advogado = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    data_emissao = db.Column(db.Date, nullable=True)
    tipo = db.Column(db.String(50), nullable=False)  # 'fatura', 'despesa'
    details = db.Column(db.Text)  # Apenas para a descrição do documento
    valor = db.Column(db.Float, nullable=False)
    is_confirmed = db.Column(db.Boolean, default=False)  # Indica se o documento está pago
    status_cobranca = db.Column(db.String(50), default='pendente')
    numero_recibo = db.Column(db.String(50))
    data_vencimento = db.Column(db.Date, nullable=True)  # Campo para data de vencimento
    numero_cliente = db.Column(db.String(50), nullable=True)

    client = db.relationship('Client', backref='documentos_contabilisticos')
    
    @property
    def dias_atraso(self):
        """
        Retorna os dias de atraso. Se houver data de vencimento, calcula a diferença entre hoje e ela;
        caso contrário, se houver data de emissão, usa essa data; senão, retorna 0.
        """
        if self.data_vencimento:
            delta = date.today() - self.data_vencimento
            return max(delta.days, 0)
        elif self.data_emissao:
            delta = date.today() - self.data_emissao
            return max(delta.days, 0)
        return 0

    
    def __repr__(self):
        return f'<DocumentoContabilistico {self.id} - {self.tipo} - Client: {self.client.name}>'
#END MODEL DOCUMENTO CONTABILIDADE

#BEGIN MODEL HORA ADIÇÃO TAREFA, PRAZOS
class HoraAdicao(db.Model):
    __tablename__ = 'horas_adicao'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20), nullable=False)  # 'assunto', 'tarefa' ou 'prazo'
    item_id = db.Column(db.Integer, nullable=False)
    horas_adicionadas = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
#END MODEL HORA ADIÇÃO TAREFA, PRAZOS

#BEGIN MODEL NOTIFICAÇÃO
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    # ID do usuário que vai receber a notificação
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # Tipo da notificação, por exemplo: 'share_invite', 'update', 'emission'
    type = db.Column(db.String(50), nullable=False)
    # Mensagem que será exibida ao usuário
    message = db.Column(db.Text, nullable=False)
    # URL para a ação relacionada, se houver (por exemplo, link para o item atualizado ou para aceitar/recusar uma partilha)
    link = db.Column(db.String(255), nullable=True)
    # Status: se a notificação já foi lida ou não (default False = não lida)
    is_read = db.Column(db.Boolean, default=False)
    # Data e hora em que a notificação foi gerada
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # Campo extra para guardar informações adicionais (pode ser um JSON com detalhes específicos)
    extra_data = db.Column(db.Text, nullable=True)

    @property
    def extra(self):
        try:
            return json.loads(self.extra_data) if self.extra_data else {}
        except Exception:
            return {}

    def __repr__(self):
        return f"<Notification {self.id} for User {self.user_id}: {self.type}>"
#END MODEL NOTIFICAÇÃO