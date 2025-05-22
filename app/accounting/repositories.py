# app/accounting/repositories.py

from app import db
from sqlalchemy import or_
from app.clientes.models import Client, ClientShare
from app.notifications.models import Notification
from app.accounting.models import DocumentoContabilistico, TmpDocumento
from app.billing.models import BillingNota


class DocumentoRepo:
    @staticmethod
    def add(doc):
        db.session.add(doc)

    @staticmethod
    def save(doc):
        # compatível com o teu serviço que comita no fim da transação
        db.session.add(doc)
        db.session.commit()
        return doc

    @staticmethod
    def get(doc_id):
        return DocumentoContabilistico.query.get(doc_id)

    @staticmethod
    def delete(doc):
        db.session.delete(doc)
        db.session.commit()

    @staticmethod
    def query_for_manage(user):
        """
        Todos os documentos criados por este user OU
        cujos clientes foram compartilhados com ele.
        """
        return (
            DocumentoContabilistico.query
            .join(Client)
            .filter(
                or_(
                    DocumentoContabilistico.user_id == user.id,
                    Client.user_id == user.id,
                    Client.shared_with.any(id=user.id),
                    Client.shares.any(ClientShare.user_id == user.id)
                )
            )
        )

    @staticmethod
    def query_for_user(user):
        return DocumentoContabilistico.query.filter_by(user_id=user.id)

    @staticmethod
    def query_for_client(user, client):
        base = DocumentoContabilistico.query.join(Client)\
            .filter(Client.id == client.id)
        if client.user_id == user.id:
            return base
        return base.filter(
            or_(
                DocumentoContabilistico.user_id == user.id,
                Client.shared_with.any(id=user.id),
                Client.shares.any(ClientShare.user_id == user.id)
            )
        )


class ClienteRepo:
    @staticmethod
    def add(c):
        db.session.add(c)

    @staticmethod
    def save(c):
        db.session.add(c)
        db.session.commit()
        return c

    @staticmethod
    def get(client_id):
        return Client.query.get(client_id)

    @staticmethod
    def find_by_user_and_name(user_id, name):
        return Client.query.filter_by(user_id=user_id, name=name).first()

    @staticmethod
    def search(term):
        # Aqui poderás converter em paginado se quiser
        return Client.query.filter(Client.name.ilike(f"%{term}%"))


class BillingNotaRepo:
    @staticmethod
    def get(nota_id):
        return BillingNota.query.get(nota_id)

    @staticmethod
    def save(nota):
        db.session.add(nota)
        db.session.commit()
        return nota


class TmpDocumentoRepo:
    @staticmethod
    def add(tmp):
        db.session.add(tmp)

    @staticmethod
    def save(tmp):
        db.session.add(tmp)
        db.session.commit()
        return tmp

    @staticmethod
    def get(tmp_id):
        return TmpDocumento.query.get(tmp_id)

    @staticmethod
    def delete(tmp):
        db.session.delete(tmp)
        db.session.commit()


class NotificationRepo:
    @staticmethod
    def get_for_user(user):
        # continua devolvendo .all() para o context processor
        return (
            Notification.query
            .filter_by(user_id=user.id)
            .order_by(Notification.timestamp.desc())
            .all()
        )
