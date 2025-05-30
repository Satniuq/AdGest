# app/forms/query_factories.py

from flask_login import current_user
from sqlalchemy import or_

def clientes_query():
    """Retorna todos os clientes ordenados."""
    from app.clientes.models import Client
    return Client.query.order_by(Client.name).all()

def user_clients_query():
    """
    Retorna clientes onde current_user é responsável, 
    clientes partilhados consigo e clientes públicos.
    """
    from app.clientes.models import Client, ClientShare
    from sqlalchemy import or_

    user_id = current_user.id

    # Clientes do próprio user
    own = Client.query.filter(Client.user_id == user_id)
    # Clientes partilhados (ClientShare)
    shared = Client.query.join(ClientShare, Client.id == ClientShare.client_id)\
                         .filter(ClientShare.user_id == user_id)
    # Clientes públicos
    public = Client.query.filter(Client.is_public.is_(True))

    # União dos três conjuntos
    # DISTINCT para não mostrar duplicados se por acaso houver overlaps
    query = own.union(shared).union(public).order_by(Client.name).distinct(Client.id)
    return query.all()

def usuarios_query():
    """Retorna advogados ativos."""
    from app.auth.models import User
    return (
        User.query
            .filter(User.role == 'advogado')
            .order_by(User.nickname)
            .all()
    )

def processos_query():
    """Retorna processos onde current_user é lead ou co-counsel."""
    from app.processos.models import Processo, process_co_counsel

    return (
        Processo.query
        .outerjoin(
            process_co_counsel,
            Processo.id == process_co_counsel.c.process_id
        )
        .filter(
            or_(
                Processo.lead_attorney_id == current_user.id,
                process_co_counsel.c.attorney_id == current_user.id
            )
        )
        .order_by(Processo.external_id)
        .distinct()
        .all()
    )
