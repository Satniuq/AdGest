# app/assuntos/services.py

from datetime import datetime, date
from typing import List
from app.auth.models import User
from sqlalchemy import or_, func
from flask import url_for
from app import db
from app.assuntos.models import Assunto, AssuntoHistory, shared_assuntos, AssuntoNote
from app.notifications.routes import criar_notificacao
from app.notifications.models import Notification
from app.tarefas.models import Tarefa, TarefaHistory
from app.models_main import HourEntry
from app.auth.models import User

class AssuntoService:

    @staticmethod
    def list_filtered(
        user_id: int,
        client_id: int | None = None,
        due_date: date | None = None,
        sort: str = 'asc'
    ) -> tuple[list[Assunto], dict[int, float]]:
        """
        Retorna a lista de Assuntos filtrada (apenas os de propriedade do user_id
        ou compartilhados com ele) e um dicionário {assunto_id: total_horas}
        calculado a partir de HourEntry.
        """
        # 1) filtra apenas assuntos do usuário ou compartilhados com ele
        q = Assunto.query.filter(
            or_(
                Assunto.owner_id == user_id,
                Assunto.shared_with.any(User.id == user_id)
            )
        )

        # 2) demais filtros opcionais
        if client_id:
            q = q.filter_by(client_id=client_id)
        if due_date:
            q = q.filter(Assunto.due_date == due_date)

        # 3) ordenação por data de vencimento
        order = (
            Assunto.due_date.asc()  if sort == 'asc'
            else Assunto.due_date.desc()
        )
        assuntos = q.order_by(order).all()

        # --- Soma de horas via HourEntry ---
        assunto_ids = [a.id for a in assuntos]
        entries = (
            HourEntry.query
            .filter_by(object_type='assunto')
            .filter(HourEntry.object_id.in_(assunto_ids))
            .all()
        )

        hours_map = {aid: 0.0 for aid in assunto_ids}
        for e in entries:
            hours_map[e.object_id] += e.hours

        return assuntos, hours_map

    @staticmethod
    def available_users(user_id: int):
        """Retorna todos os usuários, menos o próprio."""
        user = User.query.get(user_id)
        if not user:
            return []

        # agora usamos `user.id`, não `current_user.id`
        return (
            User.query
                .filter(User.id != user.id)
                .order_by(User.nickname)
                .all()
        )
    
    @staticmethod
    def list_for_user(user_id: int):
        qs = Assunto.query.filter(
            or_(
                Assunto.owner_id == user_id,
                Assunto.shared_with.any(id=user_id)
            )
        ).order_by(Assunto.sort_order, Assunto.title)
        return qs.all()

    @staticmethod
    def get_or_404(id_):
        return Assunto.query.get_or_404(id_)

    @staticmethod
    def create(data, user):
        # só importamos Client quando precisamos
        from app.clientes.models import Client

        # 1) resolve cliente
        if data.get("client_existing"):
            client = data["client_existing"]
        else:
            client = Client(user_id=user.id, name=data["client_new"].strip())
            db.session.add(client)
            db.session.commit()

        # 2) cria Assunto
        a = Assunto(
            title       = data["title"],
            description = data.get("description"),
            owner_id    = user.id,
            client_id   = client.id,
            due_date    = data.get("due_date"),
            sort_order  = data.get("sort_order", 0)
        )
        a.shared_with = data.get("shared_with", [])
        db.session.add(a)
        db.session.commit()

        # 3) histórico
        AssuntoService._snapshot(a, user, "created", {
            "title":       a.title,
            "description": a.description,
            "due_date":    str(a.due_date) if a.due_date else None,
            "sort_order":  a.sort_order,
            "client_id":   a.client_id
        })

        # 4) notifica compartilhados
        AssuntoService._notify(a, user, "created")
        return a

    @staticmethod
    def update(a: Assunto, data, user):
        from app.clientes.models import Client

        # 1) snapshot antes
        old = {
            "title":       a.title,
            "description": a.description,
            "due_date":    a.due_date,
            "sort_order":  a.sort_order,
            "client_id":   a.client_id
        }

        # 2) atualiza campos
        a.title       = data["title"]
        a.description = data.get("description")
        a.due_date    = data.get("due_date")
        a.sort_order  = data.get("sort_order", 0)

        # 3) atualiza cliente
        if data.get("client_existing"):
            a.client_id = data["client_existing"].id
        else:
            cli = Client(user_id=user.id, name=data["client_new"].strip())
            db.session.add(cli)
            db.session.commit()
            a.client_id = cli.id

        # 5) calcula diff e grita histórico/notify
        new = {
            "title":       a.title,
            "description": a.description,
            "due_date":    a.due_date,
            "sort_order":  a.sort_order,
            "client_id":   a.client_id
        }
        diff = {
            k: {"old": old[k], "new": new[k]}
            for k in old if old[k] != new[k]
        }
        if diff:
            AssuntoService._snapshot(a, user, "updated", diff)
            AssuntoService._notify(a, user, "updated")

        return a

    @staticmethod
    def share(a: Assunto, users: List[User], current_user):
        """
        Acrescenta à relação shared_with somente os usuários
        que ainda não estavam lá, e registra histórico.
        """
        # ids já existentes
        current_ids = {u.id for u in a.shared_with}

        # identifique só os novos
        to_add = [u for u in users if u.id not in current_ids]

        # anexe cada um
        for u in to_add:
            a.shared_with.append(u)

        # persista
        db.session.commit()

        # histórico: quem entrou e estado final
        payload = {
            'added':  [u.id for u in to_add],
            'all_ids':[u.id for u in a.shared_with]
        }
        AssuntoService._snapshot(
            a,
            current_user,
            'share',
            payload
        )
        AssuntoService._notify(a, current_user, 'share')

    @staticmethod
    def toggle_status(a: Assunto, user):
        # alterna status e marca completed_at/by
        if a.status == "open":
            a.status = "done"
            a.completed_at = datetime.utcnow()
            a.completed_by = user.id
            # marca todas as tarefas pendentes
            for t in a.tarefas:
                if t.status != "done":
                    from app.tarefas.services import TarefaService
                    TarefaService.toggle_status(t, user)
        else:
            a.status = "open"
            a.completed_at = None
            a.completed_by = None

        db.session.commit()
        AssuntoService._snapshot(a, user, "status_changed", {"new_status": a.status})
        AssuntoService._notify(a, user, "status_changed")
        return a

    

    @staticmethod
    def delete(a: Assunto, user):
        # notifica antes de excluir
        envolvidos = set([a.owner] + a.shared_with.all())
        # remove links many-to-many
        db.session.execute(shared_assuntos.delete().where(shared_assuntos.c.assunto_id == a.id))
        db.session.delete(a)
        db.session.commit()

        for u in envolvidos:
            if u.id != user.id:
                criar_notificacao(
                    u.id,
                    "deleted",
                    f"{user.nickname} excluiu o assunto '{a.title}'.",
                    url_for('dashboard.dashboard')
                )

    @staticmethod
    def _snapshot(a: Assunto, user, change_type: str, serialized: dict):
        import json
        hist = AssuntoHistory(
            assunto_id      = a.id,
            change_type     = change_type,
            changed_at      = datetime.utcnow(),
            changed_by      = user.id,
            serialized_data = json.dumps(serialized, default=str),
        )
        db.session.add(hist)
        db.session.commit()

    @staticmethod
    def _notify(a: Assunto, user, action: str):
        msg_map = {
            "created":        "criou o assunto",
            "updated":        "editou o assunto",
            "status_changed": "alterou status do assunto",
            "share":          "compartilhou o assunto"
        }
        texto = f"{user.nickname} {msg_map[action]} '{a.title}'."
        link  = url_for('assuntos.history', id=a.id)
        envolvidos = set([a.owner] + a.shared_with.all())
        envolvidos.discard(user)

        for u in envolvidos:
            criar_notificacao(u.id, "update", texto, link)

    @staticmethod
    def add_note(assunto, content, user):
        """
        Cria um AssuntoNote ligado ao assunto e ao usuário.
        """
        note = AssuntoNote(
            assunto_id=assunto.id,
            user_id=user.id,
            content=content
        )
        db.session.add(note)
        db.session.commit()
        return note