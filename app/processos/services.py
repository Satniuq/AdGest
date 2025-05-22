# app/processos/services.py

from datetime import datetime, date
from typing import List, Dict
from flask import url_for 
from app import db
from app.auth.models import User
from app.processos.models import (
    Processo,
    CaseType,
    Phase,
    PracticeArea,
    Court,
    Tag,
    ProcessoHistory
)
from app.notifications.routes import criar_notificacao

class ProcessoService:
    @staticmethod
    def list_for_user(
        user_id: int,
        client_id: int = None,
        case_type_id: int = None,
        phase_id: int = None,
        practice_area_id: int = None,
        court_id: int = None,
        status: str = None
    ) -> List[Processo]:
        user = User.query.get(user_id)
        if user and user.role == 'admin':
            q = Processo.query
        else:
            q = Processo.query.filter(
                (Processo.lead_attorney_id == user_id) |
                Processo.shared_with.any(User.id == user_id)
            )

        if client_id:
            q = q.filter(Processo.client_id == client_id)
        if case_type_id:
            q = q.filter(Processo.case_type_id == case_type_id)
        if phase_id:
            q = q.filter(Processo.phase_id == phase_id)
        if practice_area_id:
            q = q.filter(Processo.practice_area_id == practice_area_id)
        if court_id:
            q = q.filter(Processo.court_id == court_id)
        if status:
            q = q.filter(Processo.status == status)

        return q.order_by(Processo.opened_at.desc()).all()

    @staticmethod
    def get(processo_id: int) -> Processo:
        return Processo.query.get_or_404(processo_id)

    @staticmethod
    def create(data: Dict, user_id: int) -> Processo:
        proc = Processo(
            external_id      = data.get('external_id'),
            case_type_id     = data.get('case_type_id'),
            phase_id         = data.get('phase_id'),
            practice_area_id = data['practice_area_id'],
            court_id         = data['court_id'],
            lead_attorney_id = data['lead_attorney_id'],
            client_id        = data['client_id'],
            status           = data.get('status', 'open'),
            opposing_party   = data.get('opposing_party'),
            value_estimate   = data.get('value_estimate'),
            opened_at        = data.get('opened_at', datetime.utcnow()),
            closed_at        = data.get('closed_at')
        )
        if 'co_counsel_ids' in data:
            proc.co_counsel = User.query.filter(User.id.in_(data['co_counsel_ids'])).all()
        if 'tag_ids' in data:
            proc.tags = Tag.query.filter(Tag.id.in_(data['tag_ids'])).all()

        db.session.add(proc)
        db.session.commit()

        # serializa snapshot convertendo datas para ISO
        snapshot = {}
        for col in proc.__table__.columns:
            val = getattr(proc, col.name)
            if isinstance(val, (datetime, date)):
                snapshot[col.name] = val.isoformat()
            else:
                snapshot[col.name] = val

        history = ProcessoHistory(
            processo_id  = proc.id,
            change_type  = 'create',
            changed_at   = datetime.utcnow(),
            changed_by   = user_id,
            snapshot     = snapshot
        )
        db.session.add(history)
        db.session.commit()

        return proc

    @staticmethod
    def update(proc: Processo, data: Dict, user_id: int) -> Processo:
        # cria snapshot serializável antes da alteração
        snapshot = {}
        for col in proc.__table__.columns:
            val = getattr(proc, col.name)
            if isinstance(val, (datetime, date)):
                snapshot[col.name] = val.isoformat()
            else:
                snapshot[col.name] = val

        # campos a ignorar na comparação direta
        skip_fields = {'co_counsel_ids', 'tag_ids'}
        changes = {}
        for field, new in data.items():
            if field in skip_fields:
                continue
            old = getattr(proc, field)
            if old != new:
                changes[field] = (old, new)
                setattr(proc, field, new)
        proc.updated_at = datetime.utcnow()

        # atualiza relacionamentos many-to-many
        if 'co_counsel_ids' in data:
            proc.co_counsel = User.query.filter(User.id.in_(data['co_counsel_ids'])).all()
        if 'tag_ids' in data:
            proc.tags = Tag.query.filter(Tag.id.in_(data['tag_ids'])).all()

        db.session.commit()

        # registra histórico de atualização
        for field, (old, new) in changes.items():
            history = ProcessoHistory(
                processo_id  = proc.id,
                change_type  = 'update',
                changed_at   = datetime.utcnow(),
                changed_by   = user_id,
                snapshot     = snapshot
            )
            db.session.add(history)
        db.session.commit()

        return proc

    @staticmethod
    def share(processo: Processo, user_ids: List[int], changed_by: int):
        """
        Acrescenta à relação shared_with apenas os usuários não
        previamente compartilhados e registra o histórico.
        """
        # 1) IDs já existentes
        current_ids = {u.id for u in processo.shared_with}

        # 2) IDs selecionados agora menos já existentes = só os novos
        to_add_ids = set(user_ids) - current_ids

        # 3) busca e anexa cada usuário novo
        if to_add_ids:
            new_users = User.query.filter(User.id.in_(to_add_ids)).all()
            for u in new_users:
                processo.shared_with.append(u)

            # 4) persiste no banco
            db.session.commit()

            # 5) registra histórico detalhado
            payload = {
                'added':   [u.id for u in new_users],
                'all_ids': [u.id for u in processo.shared_with]
            }
            history = ProcessoHistory(
                processo_id = processo.id,
                change_type = 'share',
                changed_at  = datetime.utcnow(),
                changed_by  = changed_by,
                snapshot    = payload
            )
            db.session.add(history)
            db.session.commit()

            # 4) Dispara notificações: informe cada usuário adicionado
            actor = User.query.get(changed_by).nickname
            texto = f"{actor} compartilhou o processo “{processo.external_id or processo.id}”."
            link  = url_for('processos.detail_process', processo_id=processo.id)
            for u in new_users:
                criar_notificacao(u.id, 'update', texto, link)


    @staticmethod
    def toggle_status(proc: Processo, user_id: int) -> str:
        # alterna o status
        proc.status = 'closed' if proc.status == 'open' else 'open'
        proc.updated_at = datetime.utcnow()
        db.session.commit()

        # serializa snapshot convertendo datas para ISO
        snapshot = {}
        for col in proc.__table__.columns:
            val = getattr(proc, col.name)
            if isinstance(val, (datetime, date)):
                snapshot[col.name] = val.isoformat()
            else:
                snapshot[col.name] = val

        # registra no histórico
        history = ProcessoHistory(
            processo_id = proc.id,
            change_type = 'toggle_status',
            changed_at  = datetime.utcnow(),
            changed_by  = user_id,
            snapshot    = snapshot
        )
        db.session.add(history)
        db.session.commit()

        return proc.status


    @staticmethod
    def delete(proc: Processo):
        db.session.delete(proc)
        db.session.commit()

    @staticmethod
    def list_case_types() -> List[CaseType]:
        return CaseType.query.order_by(CaseType.name).all()

    @staticmethod
    def list_phases(case_type_id: int) -> List[Phase]:
        return Phase.query.filter_by(case_type_id=case_type_id).order_by(Phase.sort_order).all()

    @staticmethod
    def list_practice_areas() -> List[PracticeArea]:
        return PracticeArea.query.order_by(PracticeArea.name).all()

    @staticmethod
    def list_courts() -> List[Court]:
        return Court.query.order_by(Court.name).all()

    @staticmethod
    def list_tags() -> List[Tag]:
        return Tag.query.order_by(Tag.name).all()
