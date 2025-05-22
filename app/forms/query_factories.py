# app/forms/query_factories.py

from flask_login import current_user
from sqlalchemy import or_

def clientes_query():
    """Retorna todos os clientes ordenados."""
    from app.clientes.models import Client
    return Client.query.order_by(Client.name).all()

def user_clients_query():
    """Retorna clientes onde current_user é responsável."""
    from app.clientes.models import Client
    return (
        Client.query
        .filter(Client.user_id == current_user.id)
        .order_by(Client.name)
        .all()
    )

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
