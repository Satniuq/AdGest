# app/tarefas/services.py
import json
from datetime import datetime, date, timedelta
from sqlalchemy import or_, func
from flask import url_for
from app import db
from app.tarefas.models import Tarefa, TarefaHistory, TarefaBillingItem, TarefaNote
from app.models_main import HoraAdicao



class TarefaService:

    @staticmethod
    def available_users(user):
        from app.assuntos.services import AssuntoService
        # por padrão as mesmas pessoas que em Assunto
        return AssuntoService.available_users(user)

    @staticmethod
    def list_for_assunto(assunto):
        return (
            Tarefa.query
                .filter(
                    Tarefa.assunto_id == assunto.id,
                    Tarefa.status      == 'open'
                )
                .order_by(Tarefa.sort_order)
                .all()
        )


    @staticmethod
    def get_or_404(id_):
        return Tarefa.query.get_or_404(id_)

    @staticmethod
    def list_for_user(user):
        from app.assuntos.models import Assunto
        return (
            Tarefa.query
            .join(Tarefa.assunto)
            .filter(
                or_(
                    Tarefa.owner_id == user.id,
                ),
                Tarefa.status == 'open'
            )
            .order_by(Tarefa.due_date)
            .all()
        )

    @staticmethod
    def create(data, user, assunto):
        t = Tarefa(
            title         = data["title"],
            description   = data.get("description"),
            owner_id      = user.id,
            assunto_id    = assunto.id,
            due_date      = data["due_date"],
            sort_order    = data.get("sort_order", 0),
            hours_estimate= data.get("hours_estimate"),
            status        = data.get("status", "open"),
            reminder_offset   = data.get("reminder_offset", 0),
        )
        t.shared_with = data.get("shared_with", [])
        db.session.add(t)
        db.session.commit()
        TarefaService._snapshot(t, user, "created", {
            "title": t.title,
            "due_date": str(t.due_date),
            "sort_order": t.sort_order,
            "hours_estimate": t.hours_estimate,
            "status": t.status
        })
        TarefaService._notify(t, user, "created")
        return t

    @staticmethod
    def update(t: Tarefa, data, user):
        old = {f: getattr(t, f) for f in ("title","description","due_date","sort_order","hours_estimate","status")}
        t.title          = data["title"]
        t.description    = data.get("description")
        t.due_date       = data["due_date"]
        t.sort_order     = data.get("sort_order", 0)
        t.hours_estimate = data.get("hours_estimate")
        t.status         = data.get("status")
        t.reminder_offset    = data.get("reminder_offset", 0)
        t.recurrence_rule_id = data.get("recurrence_rule").id if data.get("recurrence_rule") else None
        t.shared_with    = data.get("shared_with", [])
        db.session.commit()
        new = {f: getattr(t, f) for f in old}
        diff = {k: {"old": old[k], "new": new[k]} for k in old if old[k] != new[k]}
        if diff:
            TarefaService._snapshot(t, user, "updated", diff)
            TarefaService._notify(t, user, "updated")
        return t

    @staticmethod
    def toggle_status(t: Tarefa, user):
        if t.status == "open":
            t.status = "done"
            t.completed_at = datetime.utcnow()
            t.completed_by = user.id
        else:
            t.status = "open"
            t.completed_at = None
            t.completed_by = None
        db.session.commit()
        TarefaService._snapshot(t, user, "status_changed", {"new_status": t.status})
        TarefaService._notify(t, user, "status_changed")
        return t

    @staticmethod
    def add_hours(t, hours, user, description=None):
        entry = HoraAdicao(
            item_type='tarefa',
            item_id=t.id,
            horas_adicionadas=hours,
            user_id=user.id
        )
        db.session.add(entry)
        db.session.commit()

        detail_text = description or f'+{hours:.1f}h'
        payload = {"added": hours, "description": description} if description else {"added": hours}
        hist = TarefaHistory(
            tarefa_id=t.id,
            change_type='hours_added',
            changed_at=datetime.utcnow(),
            changed_by=user.id,
            user_id=user.id,
            serialized_data=json.dumps(payload),
            detail=detail_text
        )
        db.session.add(hist)
        db.session.commit()
        return entry

    
    @staticmethod
    def total_hours_for_assunto(assunto):
        """
        Retorna o total de horas estimadas (ou registradas) para todas as tarefas
        vinculadas a este Assunto.
        """
        # supondo que 'assunto' seja um objeto Assunto já carregado
        # e que cada tarefa tenha um atributo 'hours_estimate'
        total = 0.0
        for tarefa in assunto.tarefas:
            if tarefa.hours_estimate:
                total += tarefa.hours_estimate
        return total

    @staticmethod
    def delete(t: Tarefa, user):
        envolvidos = set([t.owner] + t.shared_with.all())
        db.session.delete(t)
        db.session.commit()
        for u in envolvidos:
            if u.id != user.id:
                criar_notificacao(u.id, "deleted",
                                  f"{user.nickname} excluiu a tarefa '{t.title}'.",
                                  url_for('assuntos.index'))
   
    
    @staticmethod
    def find_by_title(title: str, user_id: int, assunto_id: int = None):
        """
        Retorna a primeira tarefa com o mesmo título para o mesmo usuário (e, se dado,
        dentro do mesmo assunto). Útil para validação de unicidade.
        """
        q = Tarefa.query.filter(
            Tarefa.owner_id == user_id,
            Tarefa.title == title
        )
        if assunto_id is not None:
            q = q.filter(Tarefa.assunto_id == assunto_id)
        return q.first()

    @staticmethod
    def _notify(t: Tarefa, user, action:str):
        from app.notifications.routes import criar_notificacao
        from app.assuntos.services import AssuntoService
        msg_map = {
            "created": "criou a tarefa",
            "updated": "editou a tarefa",
            "status_changed": "alterou status da tarefa",
            "hours_added": "adicionou horas na tarefa"
        }
        txt = f"{user.nickname} {msg_map[action]} '{t.title}'."
        link = url_for('assuntos.history', id=t.assunto_id)
        envolvidos = set([t.assunto.owner] + t.assunto.shared_with.all())
        envolvidos.discard(user)
        for u in envolvidos:
            criar_notificacao(u.id, "update", txt, link)
    
    @staticmethod
    def add_note(tarefa, content, user):
        note = TarefaNote(
            tarefa_id = tarefa.id,
            user_id   = user.id,
            content   = content
        )
        db.session.add(note)
        db.session.commit()
        return note

    @staticmethod
    def add_billing_item(tarefa, history_id, hours, description, user):
        bi = TarefaBillingItem(
            tarefa_id   = tarefa.id,
            history_id  = history_id,
            hours       = hours,
            description = description,
            created_by  = user.id,
            invoiced    = False   # explicita
        )
        db.session.add(bi)
        db.session.commit()
        return bi

    @staticmethod
    def remove_billing_item(item_id):
        item = TarefaBillingItem.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()

    @staticmethod
    def list_billing_items(tarefa_id):
        return (
            TarefaBillingItem.query
                .filter_by(tarefa_id=tarefa_id)
                .order_by(TarefaBillingItem.created_at)
                .all()
        )
    
    @staticmethod
    def list_pending_billing_items(tarefa_id):
        """Só os billing_items ainda não faturados."""
        return (
            TarefaBillingItem.query
                .filter_by(tarefa_id=tarefa_id, invoiced=False)
                .order_by(TarefaBillingItem.created_at)
                .all()
        )

    @staticmethod
    def list_all_billing_items(tarefa_id):
        """Todos os billing_items criados, para o histórico (✓)."""
        return (
            TarefaBillingItem.query
                .filter_by(tarefa_id=tarefa_id)
                .order_by(TarefaBillingItem.created_at)
                .all()
        )

    @staticmethod
    def unbilled_hours(tarefa):
        billed = sum(item.hours for item in tarefa.billing_items)
        spent  = sum(h.horas_adicionadas for h in tarefa.additions)
        return max(0.0, spent - billed)

    @staticmethod
    def task_total_hours(t):
        adicional = db.session.query(
            func.coalesce(func.sum(HoraAdicao.horas_adicionadas), 0.0)
        ).filter_by(item_type='tarefa', item_id=t.id).scalar()
        return (t.hours_estimate or 0.0) + adicional

    @staticmethod
    def _snapshot(t, user, change_type, diff):
        import json
        hist = TarefaHistory(
            tarefa_id       = t.id,
            change_type     = change_type,
            changed_at      = datetime.utcnow(),
            changed_by      = user.id,
            user_id         = user.id,
            serialized_data = json.dumps(diff, default=str),
            detail          = None
        )
        db.session.add(hist)
        db.session.commit()

    @staticmethod
    def list_filtered(
        user_id: int,
        client_id: int | None = None,
        due_date: date | None = None,
        status: str | None = None,
        sort: str = 'nearest'
    ) -> tuple[list[Tarefa], dict[int, float]]:
        """
        Retorna só as tarefas cujo owner_id == user_id
        ou onde shared_with inclui user_id, e aplica filtros
        de cliente, data, status e ordenação.
        """
        from app.assuntos.models import Assunto
        from app.auth.models     import User
        
        # 1) filtra por permissão (propriedade OU compartilhamento)
        q = (
            Tarefa.query
            .join(Assunto)
            .filter(
                or_(
                    Tarefa.owner_id == user_id,
                    Tarefa.shared_with.any(User.id == user_id)
                )
            )
        )

        # 2) filtros adicionais
        if client_id:
            q = q.filter(Assunto.client_id == client_id)
        if due_date:
            q = q.filter(Tarefa.due_date == due_date)
        if status:
            q = q.filter(Tarefa.status == status)

        # 3) ordenação
        if sort == 'nearest':
            q = q.order_by(Tarefa.due_date.asc())
        else:
            q = q.order_by(Tarefa.due_date.desc())

        tarefas = q.all()

        # 4) soma de horas via HoraAdicao
        ids = [t.id for t in tarefas]
        entries = (
            HoraAdicao.query
            .filter_by(item_type='tarefa')
            .filter(HoraAdicao.item_id.in_(ids))
            .all()
        )
        task_hours = {i: 0.0 for i in ids}
        for e in entries:
            task_hours[e.item_id] += e.horas_adicionadas

        return tarefas, task_hours

    @staticmethod
    def group_by_assunto(assunto_ids):
        tarefas = Tarefa.query.filter(Tarefa.assunto_id.in_(assunto_ids)).all()
        ids = [t.id for t in tarefas]
        entries = HoraAdicao.query.filter_by(item_type='tarefa').filter(HoraAdicao.item_id.in_(ids)).all()
        visible  = {}
        hours_map = {i:0.0 for i in ids}
        for t in tarefas:
            visible.setdefault(t.assunto_id, []).append(t)
        for e in entries:
            hours_map[e.item_id] += e.horas_adicionadas
        return visible, hours_map
    
    @staticmethod
    def gerar_nota_honorarios(tarefa):
        from flask_login import current_user
        from app.billing.models import BillingNota, BillingNotaItem
        from app.tarefas.models import (
            NotaHonorarios,
            NotaHonorariosItem,
            TarefaBillingItem
        )
        from app.processos.models import Processo
        from app.clientes.models import Client

        # 1) busca só os billing items pendentes
        items_to_invoice = (
            TarefaBillingItem.query
                .filter_by(tarefa_id=tarefa.id, invoiced=False)
                .order_by(TarefaBillingItem.created_at)
                .all()
        )

        # 2) soma apenas essas horas
        total = sum(bi.hours for bi in items_to_invoice)

        # 3) cria o cabeçalho da nota com total correto
        nota = NotaHonorarios(
            tarefa_id   = tarefa.id,
            created_by  = current_user.id,
            total_hours = total
        )
        db.session.add(nota)
        db.session.flush()  # para ter nota.id

        # 4) snapshot + marcação de cada item
        for bi in items_to_invoice:
            nh_item = NotaHonorariosItem(
                nota_id     = nota.id,
                date        = bi.history.changed_at,
                user_id     = bi.history.user_id,
                hours       = bi.hours,
                description = bi.description or bi.history.detail
            )
            db.session.add(nh_item)

            # marca como faturado
            bi.invoiced = True
            db.session.add(bi)

        db.session.commit()

        # Extrai diretamente o client_id do Assunto
        client_id = tarefa.assunto.client_id

        billing = BillingNota(
            source_type   = 'tarefa',
            source_id     = nota.id,
            created_by    = current_user.id,
            total_hours   = nota.total_hours,
            cliente_id    = client_id,
            status        = 'pendente'
        )
        db.session.add(billing)
        db.session.commit()

        for nh_item in nota.items:  # são PrazoNotaHonorariosItem ou NotaHonorariosItem
            bn_item = BillingNotaItem(
                nota_id     = billing.id,
                date        = nh_item.date,
                user_id     = nh_item.user_id,
                hours       = nh_item.hours,
                description = nh_item.description
            )
            db.session.add(bn_item)

        db.session.commit()

        return nota