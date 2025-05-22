# app/clientes/services.py

import csv
from io import StringIO
from typing import List, Dict, Optional, Tuple, Any
from flask import current_app, url_for, abort
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.clientes.models import Client, ClientShare
from app.auth.models import User
from app.notifications.routes import criar_notificacao
from app.notifications.models import Notification, Comment
from app.assuntos.models import Assunto
from app.processos.models import Processo
from app.prazos.models import PrazoJudicial
from app.tarefas.models import TarefaHistory, Tarefa
from app.prazos.models import PrazoHistory
from app.utils import normalize_header


def list_clients(
    user_id: int,
    page: int = 1,
    per_page: int = 10,
    search: str = ''
):
    # escritório (públicos)
    public_q = Client.query.filter(Client.is_public.is_(True))
    # próprios (privados do utilizador)
    own_q    = Client.query.filter(Client.user_id == user_id)
    # partilhados
    shared_q = Client.query\
       .join(ClientShare, Client.id == ClientShare.client_id)\
       .filter(ClientShare.user_id == user_id)
    # união de todos
    query = public_q.union_all(own_q).union_all(shared_q)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Client.name.ilike(term),
                Client.number_interno.ilike(term)
            )
        )
    return query.order_by(func.lower(Client.name)).paginate(page=page, per_page=per_page)


def get_client_or_404(client_id: int, user_id: int) -> Client:
    client = Client.query.get_or_404(client_id)
    # permito leitura se for público, owner ou shared
    is_shared = client.shared_with.filter_by(id=user_id).first() is not None
    if not (client.is_public or client.user_id == user_id or is_shared):
        abort(404)
    return client


def create_client(
    user_id: int,
    name: str,
    number_interno: Optional[str],
    nif: Optional[str],
    address: Optional[str],
    email: Optional[str],
    telephone: Optional[str],
    shared_with: Optional[List[User]] = None,
    is_public: bool = False
) -> Client:
    client = Client(
        user_id=user_id,
        name=name.strip(),
        is_public=is_public,
        number_interno=number_interno.strip() if number_interno else None,
        nif=nif.strip() if nif else None,
        address=address.strip() if address else None,
        email=email.strip() if email else None,
        telephone=telephone.strip() if telephone else None
    )
    db.session.add(client)
    db.session.flush()  # para garantirmos client.id antes de partilhas

    if shared_with:
        for user in shared_with:
            if user.id == user_id:
                continue
            cs = ClientShare(client_id=client.id, user_id=user.id, option='info')
            db.session.add(cs)
            link = url_for('client.verify_client', client_id=client.id)
            criar_notificacao(
                user.id,
                "share_invite",
                f"{user.nickname}, o cliente {client.name} foi partilhado consigo.",
                link,
                extra_data={"cliente_id": client.id}
            )

    db.session.commit()
    return client


def update_client(
    client_id: int,
    name: str,
    is_public: bool,
    number_interno: Optional[str],
    nif: Optional[str],
    address: Optional[str],
    email: Optional[str],
    telephone: Optional[str]
) -> Client:
    client = Client.query.get_or_404(client_id)
    client.is_public = is_public
    client.name = name.strip()
    client.number_interno = number_interno.strip() if number_interno else None
    client.nif = nif.strip() if nif else None
    client.address = address.strip() if address else None
    client.email = email.strip() if email else None
    client.telephone = telephone.strip() if telephone else None
    db.session.commit()
    return client


def parse_csv(file_storage) -> List[Dict[str, str]]:
    sample = file_storage.read(1024).decode('utf-8')
    file_storage.seek(0)
    dialect = csv.Sniffer().sniff(sample)
    stream = StringIO(file_storage.read().decode('utf-8'))
    reader = csv.DictReader(stream, dialect=dialect)
    registros: List[Dict[str, str]] = []
    for row in reader:
        registros.append({
            normalize_header(k): (v.strip() if v else '')
            for k, v in row.items()
        })
    return registros


def import_clients(
    user_id: int,
    registros: List[Dict[str, str]]
) -> int:
    """
    Para cada linha do CSV:
    1. Se encontrar um Client existente por NIF ou number_interno, atualiza TODOS os campos (exceto nome, 
       se o novo nome conflitar com outro cliente).
    2. Se não encontrar, cria um novo Client; se o nome conflitar, adiciona sufixo "(2)", "(3)"...
    Retorna o número de registros processados.
    """
    def name_conflicts(name: str, exclude_id: Optional[int] = None) -> bool:
        q = Client.query.filter(Client.user_id == user_id, Client.name == name)
        if exclude_id:
            q = q.filter(Client.id != exclude_id)
        return q.first() is not None

    def make_unique_name(base: str) -> str:
        suffix = 1
        candidate = base
        while name_conflicts(candidate):
            suffix += 1
            candidate = f"{base} ({suffix})"
        return candidate

    count = 0
    for row in registros:
        # Extrai e normaliza os campos
        name = (row.get('client') or row.get('cliente') or
                row.get('name') or row.get('nome') or '').strip()
        if not name:
            continue

        number_interno = (row.get('number_interno') or row.get('numero_interno') or '').strip()
        nif = row.get('nif', '').strip()
        address = (row.get('address') or row.get('endereco') or '').strip()
        email = row.get('email', '').strip()
        telephone = (row.get('telephone') or row.get('telefone') or '').strip()

        # 1) tenta achar por NIF ou Nº interno
        client = None
        if nif:
            client = Client.query.filter_by(nif=nif, user_id=user_id).first()
        if not client and number_interno:
            client = Client.query.filter_by(
                number_interno=number_interno, user_id=user_id
            ).first()

        if client:
            # Marca sempre como público
            client.is_public = True
            # Atualiza campos: nome só se não conflitar
            if name and name != client.name and not name_conflicts(name, exclude_id=client.id):
                client.name = name
            # Mantém o antigo name se conflitar ou estiver vazio
            client.number_interno = number_interno or client.number_interno
            client.nif = nif or client.nif
            client.address = address or client.address
            client.email = email or client.email
            client.telephone = telephone or client.telephone

        else:
            # 2) cria novo Cliente
            new_name = name
            if name_conflicts(new_name):
                new_name = make_unique_name(new_name)

            client = Client(
                user_id=user_id,
                name=new_name,
                is_public=True,
                number_interno=number_interno or None,
                nif=nif or None,
                address=address or None,
                email=email or None,
                telephone=telephone or None
            )
            db.session.add(client)

        count += 1

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao importar clientes: {e}")
        # relança para a rota poder mostrar flash apropriado
        raise

    return count



def share_client(
    client: Client,
    shared_users: List[User],
    inviter: User
) -> None:
    # Partilha imediata: cria ClientShare se não existir e notifica
    for user in shared_users:
        if user.id == inviter.id:
            continue

        # Só adiciona se ainda não partilhado
        exists = ClientShare.query.filter_by(
            client_id=client.id,
            user_id=user.id
        ).first()
        if not exists:
            cs = ClientShare(
                client_id=client.id,
                user_id=user.id,
                option='info'
            )
            db.session.add(cs)

        # Notificação direta para a página de detalhe do cliente
        link = url_for('client.client_info', client_id=client.id, _external=True)
        criar_notificacao(
            user.id,
            "share",
            f"{inviter.nickname} partilhou consigo o cliente “{client.name}”",
            link,
            extra_data={"cliente_id": client.id}
        )

    db.session.commit()


def get_client_history(client_id: int, user_id: int) -> Dict[str, Any]:
    # 1. Carrega o cliente, garantindo permissão
    client = get_client_or_404(client_id, user_id)

    # 2. Busca Assuntos (concluídos e pendentes) pelo mesmo number_interno
    assuntos_concluidos = (
        Assunto.query
        .join(Assunto.client)
        .filter(
            Client.number_interno == client.number_interno,
            Assunto.status == 'closed',
            or_(
                Assunto.owner_id == user_id,
                Assunto.shared_with.any(User.id == user_id)
            )
        )
        .all()
    )
    assuntos_pendentes = (
        Assunto.query
        .join(Assunto.client)
        .filter(
            Client.number_interno == client.number_interno,
            Assunto.status == 'open',
            or_(
                Assunto.owner_id == user_id,
                Assunto.shared_with.any(User.id == user_id)
            )
        )
        .all()
    )

    # 3. Busca Prazos (concluídos e pendentes) pelo mesmo number_interno
    prazos_concluidos = (
        PrazoJudicial.query
        .filter(
            PrazoJudicial.client_id == client.id,
            PrazoJudicial.status == 'closed',
            or_(
                PrazoJudicial.owner_id == user_id,
                PrazoJudicial.shared_with.any(User.id == user_id)
            )
        )
        .order_by(PrazoJudicial.date)
        .all()
    )
    prazos_pendentes = (
        PrazoJudicial.query
        .filter(
            PrazoJudicial.client_id == client.id,
            PrazoJudicial.status == 'open',
            or_(
                PrazoJudicial.owner_id == user_id,
                PrazoJudicial.shared_with.any(User.id == user_id)
            )
        )
        .all()
    )

    # 4. Busca Processos pelo mesmo cliente
    processos = (
        Processo.query
        .filter(Processo.client_id == client.id,)
        .order_by(Processo.opened_at.desc())
        .all()
    )

    # 5. BUSCA DE TAREFAS RELACIONADAS A ESTE CLIENTE
    #    via Assunto.client_id == client.id
    tarefas = (
        Tarefa.query
        .join(Tarefa.assunto)
        .filter(
            Assunto.client_id == client.id,
            or_(
                Tarefa.owner_id == user_id,
                Tarefa.shared_with.any(User.id == user_id)
            )
        )
        .order_by(Tarefa.due_date)
        .all()
    )
    # 6. MONTA HISTÓRICO DE CADA TAREFA
    tarefas_history = {
        t.id: (
            TarefaHistory.query
            .filter_by(tarefa_id=t.id)
            .order_by(TarefaHistory.changed_at.desc())
            .all()
        )
        for t in tarefas
    }

    return {
        'client': client,
        'assuntos_pendentes': assuntos_pendentes,
        'assuntos_concluidos': assuntos_concluidos,
        'prazos_pendentes': prazos_pendentes,
        'prazos_concluidos': prazos_concluidos,
        'processos': processos,
        'tarefas': tarefas,
        'tarefas_history': tarefas_history
    }