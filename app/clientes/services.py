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
from app.billing.models import BillingNota
from app.accounting.models import DocumentoContabilistico
from sqlalchemy.exc import NoResultFound


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
    # lê todo o conteúdo e tenta decodificar mantendo BOM
    content = file_storage.read()
    for enc in ('utf-8-sig', 'utf-8', 'latin1'):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    # sample para sniff
    sample = text[:1024]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=';,')
    except csv.Error:
        # fallback para ponto-e-vírgula
        dialect = csv.excel()
        dialect.delimiter = ';'
    # cria o reader a partir do texto já decodificado
    stream = StringIO(text)
    reader = csv.DictReader(stream, dialect=dialect)

    registros: List[Dict[str, str]] = []
    for row in reader:
        registros.append({
            normalize_header(k): (v.strip() if v else '')
            for k, v in row.items()
        })
    # para ver no log exatamente o que chegou
    current_app.logger.debug(f"[CSV] registros normalizados: {registros}")
    return registros


def delete_client(client_id: int):
    """
    Remove manualmente tudo que referencia client_id, depois apaga o Client.
    """
    client = Client.query.get(client_id)
    if not client:
        raise ValueError(f"Cliente com id {client_id} não encontrado.")

    # 1) Apaga compartilhamentos de cliente
    db.session.query(ClientShare) \
        .filter(ClientShare.client_id == client_id) \
        .delete(synchronize_session=False)

    # 2) Apaga notas de faturação
    db.session.query(BillingNota) \
        .filter(BillingNota.cliente_id == client_id) \
        .delete(synchronize_session=False)

    # 3) Apaga documentos contabilísticos
    db.session.query(DocumentoContabilistico) \
        .filter(DocumentoContabilistico.client_id == client_id) \
        .delete(synchronize_session=False)

    # 4) Apaga prazos judiciais
    db.session.query(PrazoJudicial) \
        .filter(PrazoJudicial.client_id == client_id) \
        .delete(synchronize_session=False)

    # 5) Apaga processos
    db.session.query(Processo) \
        .filter(Processo.client_id == client_id) \
        .delete(synchronize_session=False)

    # 6) Apaga assuntos (tarefas ligadas a assuntos também herdam o delete)
    db.session.query(Assunto) \
        .filter(Assunto.client_id == client_id) \
        .delete(synchronize_session=False)

    # 7) Finalmente, apaga o próprio cliente
    db.session.delete(client)

    # 8) Commit único
    db.session.commit()

    return True


def import_clients(
    user_id: int,
    registros: List[Dict[str, str]]
) -> int:
    """
    Bulk import de clientes:
    - Atualiza os que já existem (por nif ou número interno).
    - Insere os novos, assegurando que o campo `name` é único por utilizador,
      criando sufixos "(2)", "(3)"… conforme necessário.
    """

    BATCH_SIZE = 1000

    # 1) Carrega todos os clientes existentes deste user
    existing_clients = (
        Client.query
        .filter_by(user_id=user_id)
        .with_entities(Client.id, Client.nif, Client.number_interno, Client.name)
        .all()
    )
    by_nif      = {c.nif: c for c in existing_clients if c.nif}
    by_internal = {c.number_interno: c for c in existing_clients if c.number_interno}

    # Conjunto de nomes já usados (existentes)
    used_names = {c.name for c in existing_clients}

    def unique_name(base: str) -> str:
        """
        Gera um nome único com base em `base`, adicionando sufixo
        "(2)", "(3)"… se necessário, e insere no used_names.
        """
        suffix = 1
        candidate = base
        while candidate in used_names:
            suffix += 1
            candidate = f"{base} ({suffix})"
        used_names.add(candidate)
        return candidate

    to_update: List[Dict] = []
    to_insert: List[Dict] = []
    count = 0

    def flush_batch():
        """Executa bulk updates e inserts, faz commit e limpa as listas."""
        if to_update:
            db.session.bulk_update_mappings(Client, to_update)
        if to_insert:
            db.session.bulk_insert_mappings(Client, to_insert)
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Erro bulk import clients: {e}")
            raise
        finally:
            to_update.clear()
            to_insert.clear()

    # 2) Itera sobre cada registro CSV
    for row in registros:
        name = (row.get('client') or row.get('cliente') or
                row.get('name')   or row.get('nome')    or '').strip()
        if not name:
            continue

        number_interno = (row.get('number_interno') or row.get('numero_interno') or '').strip() or None
        nif            = row.get('nif', '').strip() or None
        address        = (row.get('address') or row.get('endereco') or '').strip() or None
        email          = (row.get('email') or '').strip() or None
        telephone      = (row.get('telephone') or row.get('telefone') or '').strip() or None

        # Verifica se já existe por nif ou número interno
        existing = None
        if nif and nif in by_nif:
            existing = by_nif[nif]
        elif number_interno and number_interno in by_internal:
            existing = by_internal[number_interno]

        if existing:
            # Prepara mapping de update
            new_name = existing.name
            if name != existing.name and name not in used_names:
                new_name = name
                used_names.add(new_name)

            to_update.append({
                'id':               existing.id,
                'name':             new_name,
                'is_public':        True,
                'number_interno':   number_interno or existing.number_interno,
                'nif':              nif            or existing.nif,
                'address':          address        or existing.address,
                'email':            email          or existing.email,
                'telephone':        telephone      or existing.telephone,
            })
        else:
            # Gera nome único para insert
            if name in used_names:
                safe_name = unique_name(name)
            else:
                safe_name = name
                used_names.add(safe_name)

            to_insert.append({
                'user_id':         user_id,
                'name':            safe_name,
                'is_public':       True,
                'number_interno':  number_interno,
                'nif':             nif,
                'address':         address,
                'email':           email,
                'telephone':       telephone,
            })

        count += 1

        # Flush a cada BATCH_SIZE
        if count % BATCH_SIZE == 0:
            flush_batch()

    # Flush final dos restantes
    flush_batch()
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
            Assunto.client_id == client.id,
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
            Assunto.client_id == client.id,
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