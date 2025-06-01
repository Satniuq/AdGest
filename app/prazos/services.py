# app/prazos/services.py

from flask_login import current_user
from datetime import date, timedelta, datetime
from sqlalchemy import or_
from typing import List, Dict

from app import db
from app.auth.models import User
from app.prazos.models import (
    PrazoJudicial,
    DeadlineType,
    RecurrenceRule,
    PrazoHistory,
    PrazoBillingItem,
    PrazoNotaHonorarios,
    PrazoNotaHonorariosItem,
    PrazoBillingItem
)

from app.processos.models import Processo  # necessário para filtros :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}

class PrazoService:
    @staticmethod
    def get_or_404(prazo_id):
        return PrazoJudicial.query.get_or_404(prazo_id)

    @staticmethod
    def list_for_user(
        user_id: int,
        type_id: int = None,
        client_id: int = None,
        case_type_id: int = None,
        phase_id: int = None,
        practice_area_id: int = None,
        court_id: int = None,
        status: str = None
    ) -> List[PrazoJudicial]:
        query = PrazoJudicial.query \
            .join(PrazoJudicial.processo) \
            .filter(
                or_(
                    PrazoJudicial.owner_id == user_id,
                    PrazoJudicial.shared_with.any(User.id == user_id),
                    # inclui prazos dos processos compartilhados
                    PrazoJudicial.processo.has(
                        Processo.shared_with.any(User.id == user_id)
                    )
                )
            )

        # filtros específicos de prazo
        if type_id:
            query = query.filter(PrazoJudicial.type_id == type_id)
        if client_id:
            query = query.filter(PrazoJudicial.client_id == client_id)

        # filtros vindos de campos do Processo (via join acima)
        if case_type_id:
            query = query.filter(Processo.case_type_id == case_type_id)
        if phase_id:
            query = query.filter(Processo.phase_id == phase_id)
        if practice_area_id:
            query = query.filter(Processo.practice_area_id == practice_area_id)
        if court_id:
            query = query.filter(Processo.court_id == court_id)

        # — CORREÇÃO: filtrar pelo status do PRAZO, não do processo
        if status:
            query = query.filter(PrazoJudicial.status == status)

        return query.order_by(PrazoJudicial.date).all()

    @staticmethod
    def list_types_for_case(case_type_id: int):
        from app.processos.models import CaseType
        case = CaseType.query.get(case_type_id)
        if not case:
            # fallback a todos, se quiser
            return DeadlineType.query.order_by(DeadlineType.name).all()
        return case.allowed_deadlines.order_by(DeadlineType.name).all()

    @staticmethod
    def get(prazo_id: int) -> PrazoJudicial:
        return PrazoJudicial.query.get_or_404(prazo_id)

    @staticmethod
    def create(data: Dict, user_id: int) -> PrazoJudicial:
        prazo = PrazoJudicial(
            processo_id   = data['processo_id'],
            owner_id      = user_id,
            client_id     = data['client_id'],
            type_id       = data['type_id'],
            recur_rule_id = data.get('recur_rule_id'),
            date          = data['date'],
            description   = data['description'],
            comments      = data.get('comments'),
            hours_spent   = data.get('hours_spent', 0.0),
            status        = data.get('status', 'open'),
            created_at    = datetime.utcnow(),
            updated_at    = datetime.utcnow()
        )
        db.session.add(prazo)
        db.session.commit()

        return prazo

    @staticmethod
    def update(prazo: PrazoJudicial, data: Dict, user_id: int) -> PrazoJudicial:
        # cria snapshot antes da alteração
        snapshot = {}
        for col in prazo.__table__.columns:
            val = getattr(prazo, col.name)
            if isinstance(val, (date, datetime)):
                snapshot[col.name] = val.isoformat()
            else:
                snapshot[col.name] = val

        # aplica alterações
        for key, val in data.items():
            setattr(prazo, key, val)
        prazo.updated_at = datetime.utcnow()

        history = PrazoHistory(
            prazo_id    = prazo.id,
            change_type = 'update',
            changed_at  = datetime.utcnow(),
            changed_by  = user_id,
            snapshot    = snapshot
        )
        db.session.add(history)
        db.session.commit()

        return prazo

    @staticmethod
    def delete(prazo: PrazoJudicial):
        db.session.delete(prazo)
        db.session.commit()

    @staticmethod
    def add_hours(prazo: PrazoJudicial, hours: float, user_id: int, description: str = None) -> float:
        import json
        from datetime import datetime
        from app import db
        from app.prazos.models import PrazoHistory

        # 1) detalhe e payload exatos como em tarefas
        detail_text = description or f"+{hours:.1f}h"
        payload     = {"added": hours}
        if description:
            payload["description"] = description

        # prepara snapshot serializável (igual ao que você já fazia)
        snapshot = {}
        for col in prazo.__table__.columns:
            val = getattr(prazo, col.name)
            if isinstance(val, (date, datetime)):
                snapshot[col.name] = val.isoformat()
            else:
                snapshot[col.name] = val

        hist = PrazoHistory(
            prazo_id    = prazo.id,
            change_type = 'add_hours',
            changed_at  = datetime.utcnow(),
            changed_by  = user_id,
            snapshot    = payload,
            detail      = description or f'+{hours:.1f}h'
        )
        db.session.add(hist)
        # 2) atualiza o campo hours_spent
        prazo.hours_spent = (prazo.hours_spent or 0.0) + hours
        db.session.add(prazo)
        db.session.commit()

        return hist

    @staticmethod
    def list_billing_items(prazo: PrazoJudicial):
        """Retorna só os billing‐items ainda não faturados."""
        return (
            PrazoBillingItem.query
                .filter_by(prazo_id=prazo.id, invoiced=False)
                .order_by(PrazoBillingItem.created_at)
                .all()
        )

    @staticmethod
    def unbilled_hours(prazo: PrazoJudicial) -> float:
        """Total de horas ainda não enviadas ao billing."""
        billed = sum(item.hours for item in prazo.billing_items)
        spent  = prazo.hours_spent or 0.0
        return max(spent - billed, 0.0)

    @staticmethod
    def create_billing_item(
        prazo: PrazoJudicial,
        history_id,
        hours: float,
        description: str,
        user_id: int
    ) -> PrazoBillingItem:
        """
        Cria um item de billing localmente e notifica o módulo billing.
        """
        # 1) limita ao máximo pendente
        pend = PrazoService.unbilled_hours(prazo)
        to_bill = min(pend, hours)

        # 2) cria registro local
        item = PrazoBillingItem(
            prazo_id    = prazo.id,
            history_id  = history_id,
            hours       = to_bill,
            description = description,
            created_by  = user_id
        )
        db.session.add(item)
        db.session.commit()

        # 3) opcional: notifica seu módulo billing
        # billing_item = BillingService.create_item(
        #     process_id=prazo.processo_id,
        #     prazo_id=prazo.id,
        #     hours=to_bill,
        #     description=description,
        #     user_id=user_id
        # )
        # item.external_billing_id = billing_item.id
        # db.session.commit()

        return item
    
    @staticmethod
    def create_billing_items_from_history(history_ids: List[int], user_id: int):
        items = []
        for hid in history_ids:
            h = PrazoHistory.query.get(hid)
            # só cria se ainda não existir
            exists = PrazoBillingItem.query.filter_by(history_id=hid).first()
            if not h or exists:
                continue

            # extrai horas do h.detail (“+2.5h” → 2.5)
            hours = float(h.detail.strip().lstrip('+').rstrip('h'))

            item = PrazoBillingItem(
                prazo_id    = h.prazo_id,
                history_id  = hid,
                hours       = hours,
                description = f'Horário de {h.changed_at.strftime("%d/%m %H:%M")}',
                created_by  = user_id
            )
            db.session.add(item)
            items.append(item)

        db.session.commit()
        return items

    @staticmethod
    def list_with_unbilled(user_id: int):
        """Prazos do usuário que ainda têm horas não faturadas."""
        return (
            PrazoJudicial.query
            .filter(PrazoJudicial.owner_id == user_id)
            .all()
        )
        # Depois, na view ou form, use unbilled_hours(p) para filtrar > 0.


    @staticmethod
    def toggle_status(prazo: PrazoJudicial) -> str:
        prazo.status = 'closed' if prazo.status == 'open' else 'open'
        prazo.updated_at = datetime.utcnow()
        db.session.commit()
        return prazo.status

    @staticmethod
    def list_types() -> List[DeadlineType]:
        return DeadlineType.query.order_by(DeadlineType.name).all()

    @staticmethod
    def list_recurrence_rules() -> List[RecurrenceRule]:
        return RecurrenceRule.query.order_by(RecurrenceRule.name).all()

    @staticmethod
    def get_history(prazo_id: int) -> List[PrazoHistory]:
        return (
            PrazoHistory.query
            .filter_by(prazo_id=prazo_id)
            .order_by(PrazoHistory.changed_at.desc())
            .all()
        )

    @staticmethod
    def gerar_nota_honorarios(prazo: PrazoJudicial) -> PrazoNotaHonorarios:
        from app.billing.models import BillingNota, BillingNotaItem
        # 1) itens pendentes
        pendentes = PrazoService.list_billing_items(prazo)

        # 2) soma só essas horas
        total = sum(item.hours for item in pendentes)

        # 3) cria o cabeçalho da nota
        nota = PrazoNotaHonorarios(
            prazo_id    = prazo.id,
            created_by  = current_user.id,
            total_hours = total
        )
        db.session.add(nota)
        db.session.flush()

        # 4) snapshot e marcação dos items
        for bi in pendentes:
            item = PrazoNotaHonorariosItem(
                nota_id     = nota.id,
                history_id  = bi.history_id,
                date        = bi.history.changed_at,
                user_id     = bi.user.id,
                hours       = bi.hours,
                description = bi.description or bi.history.detail
            )
            db.session.add(item)
            # marca o billing item como faturado
            bi.invoiced = True
            db.session.add(bi)

        db.session.commit()

        billing = BillingNota(
            source_type='prazo',
            source_id=nota.id,
            created_by=current_user.id,
            total_hours=nota.total_hours,
            cliente_id=prazo.client_id,
            status='pendente'
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
    

