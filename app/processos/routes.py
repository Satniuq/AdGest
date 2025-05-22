#app/processos/routes.py
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_wtf import FlaskForm
from app import db
from app.auth.models import User
from app.processos import processos_bp
from app.processos.models import ProcessNote
from app.processos.forms import ProcessoForm, ShareProcessForm
from app.prazos.services import PrazoService
from app.prazos.models import PrazoJudicial
from app.processos.services import ProcessoService


class DummyForm(FlaskForm):
    """Formulário vazio apenas para gerar CSRF token"""

@processos_bp.route('/', methods=['GET'])
@login_required
def list_processes():
    # mesmos filtros que você já tinha
    client_id        = request.args.get('client_id',        type=int)
    case_type_id     = request.args.get('case_type_id',     type=int)
    phase_id         = request.args.get('phase_id',         type=int)
    practice_area_id = request.args.get('practice_area_id', type=int)
    court_id         = request.args.get('court_id',         type=int)
    status           = request.args.get('status',           type=str)

    # instância do form só com csrf
    csrf_form = DummyForm()

    # redireciona para o dashboard_prazos.manage no modo processos
    return redirect(url_for(
        'dashboard_prazos.manage',
        mode='processos',
        client_id=client_id,
        case_type_id=case_type_id,
        phase_id=phase_id,
        practice_area_id=practice_area_id,
        court_id=court_id,
        status=status,
    ))

@processos_bp.route('/<int:processo_id>', methods=['GET', 'POST'])
@login_required
def detail_process(processo_id):
    # importa os forms internamente para evitar circular imports
    from app.processos.forms import AddNoteForm
    from app.prazos.forms    import AddPrazoHoursForm
    from app.prazos.models   import PrazoHistory
    from app.processos.models import ProcessoHistory

    # Instancia os forms
    add_note_form  = AddNoteForm()
    add_hours_form = AddPrazoHoursForm()

    # Busca o processo
    processo = ProcessoService.get(processo_id)

    # 1) Nota no processo
    if add_note_form.validate_on_submit() and 'content' in request.form:
        note = ProcessNote(
            processo_id = processo.id,
            content     = add_note_form.content.data,
            created_at  = datetime.utcnow(),
            created_by  = current_user.id
        )
        db.session.add(note)
        db.session.commit()
        flash('Nota adicionada com sucesso.', 'success')
        return redirect(request.url)

    # 2) Adicionar horas a um prazo
    if add_hours_form.validate_on_submit() and 'hours' in request.form:
        horas    = add_hours_form.hours.data
        prazo_id = request.form.get('prazo_id', type=int)
        prazo    = PrazoJudicial.query.get_or_404(prazo_id)
        PrazoService.add_hours(prazo, horas, current_user.id)
        flash(f'{horas:.1f}h adicionada(s) ao Prazo #{prazo.id}.', 'success')
        return redirect(request.url)

    # 3) Carrega notas do processo
    notes = (
        ProcessNote.query
        .filter_by(processo_id=processo.id)
        .order_by(ProcessNote.created_at.desc())
        .all()
    )

    # 4) Carrega fases e identifica a atual
    phases = ProcessoService.list_phases(processo.case_type_id)
    current_phase_id = processo.phase_id

    # 5) Lista todos os prazos deste processo (para histórico consolidado)
    process_prazos = PrazoJudicial.query.filter_by(
        processo_id=processo.id
    ).all()

    # 5.1) Histórico de horas 'add_hours' por prazo
    horas_history = {}
    for prazo_item in process_prazos:
        hs = (
            PrazoHistory.query
            .filter_by(prazo_id=prazo_item.id, change_type='add_hours')
            .order_by(PrazoHistory.changed_at.desc())
            .all()
        )
        horas_history[prazo_item.id] = hs
    
    billed_history_ids = set()
    for pr in process_prazos:
        for item in pr.billing_items.all():
            billed_history_ids.add(item.history_id)

    # 6) Prazos para as abas (Pendentes/Concluídos, só deste processo)
    prazos = (
        PrazoJudicial.query
        .filter_by(processo_id=processo.id)
        .order_by(PrazoJudicial.date)
        .all()
    )

    # 7) Calcula billing (faturado / pendente) por prazo
    billing_info = {}
    for prazo in prazos:
        billed    = sum(item.hours for item in prazo.billing_items.all())
        spent     = prazo.hours_spent or 0.0
        unbilled  = max(spent - billed, 0.0)
        billing_info[prazo.id] = {
            'billed': billed,
            'unbilled': unbilled
        }

    # 8) Captura filtros para o link “Voltar”
    client_id         = request.args.get('client_id',        type=int)
    case_type_id_arg  = request.args.get('case_type_id',     type=int)
    phase_id_arg      = request.args.get('phase_id',         type=int)
    practice_area_id  = request.args.get('practice_area_id', type=int)
    court_id          = request.args.get('court_id',         type=int)
    status            = request.args.get('status',           type=str)

    last_share = (
        ProcessoHistory.query
        .filter_by(processo_id=processo.id, change_type='share')
        .order_by(ProcessoHistory.changed_at.desc())
        .first()
    )

    return render_template(
        'processos/detail.html',
        processo=processo,
        notes=notes,
        phases=phases,
        current_phase_id=current_phase_id,
        prazos=prazos,
        process_prazos=process_prazos,
        horas_history=horas_history,
        billing_info=billing_info,
        billed_history_ids=billed_history_ids,
        add_note_form=add_note_form,
        add_hours_form=add_hours_form,
        client_id=client_id,
        case_type_id=case_type_id_arg,
        phase_id=phase_id_arg,
        practice_area_id=practice_area_id,
        court_id=court_id,
        status=status,
        last_share=last_share,
    )

@processos_bp.route('/create', methods=['GET','POST'])
@login_required
def create_process():
    from app.clientes.models import Client
    form = ProcessoForm()

    # 1) Injeta todos os query_factories estáticos
    from app.forms.query_factories import usuarios_query, clientes_query
    form.client.query_factory        = clientes_query
    form.case_type.query_factory     = ProcessoService.list_case_types
    form.practice_area.query_factory = ProcessoService.list_practice_areas
    form.court.query_factory         = ProcessoService.list_courts
    form.lead_attorney.query_factory = usuarios_query
    form.co_counsel.query_factory    = usuarios_query
    form.tags.query_factory          = ProcessoService.list_tags

    # 2) Repopula o factory de 'phase' com base no case_type selecionado
    #    Isto deve vir antes do validate_on_submit!
    if form.case_type.data:
        ct_id = form.case_type.data.id
        form.phase.query_factory = lambda: ProcessoService.list_phases(ct_id)
    else:
        form.phase.query_factory = lambda: []

    # 3) Valida e, se OK, cria chamando create(data, user_id)
    if form.validate_on_submit():
        data = {
            'external_id'       : form.external_id.data or None,
            'case_type_id'      : form.case_type.data.id if form.case_type.data else None,
            'phase_id'          : form.phase.data.id if form.phase.data else None,
            'practice_area_id'  : form.practice_area.data.id,
            'court_id'          : form.court.data.id,
            'lead_attorney_id'  : form.lead_attorney.data.id,
            'client_id'         : form.client.data.id,
            'status'            : form.status.data,
            'opposing_party'    : form.opposing_party.data,
            'value_estimate'    : form.value_estimate.data,
            'opened_at'         : form.opened_at.data or datetime.utcnow(),
            'closed_at'         : form.closed_at.data,
            'co_counsel_ids'    : [u.id for u in form.co_counsel.data],
            'tag_ids'           : [t.id for t in form.tags.data],
        }
        proc = ProcessoService.create(data, current_user.id)
        flash('Processo criado com sucesso.', 'success')
        return redirect(url_for('processos.detail_process', processo_id=proc.id))

    return render_template('processos/create.html', form=form)


@processos_bp.route('/<int:processo_id>/edit', methods=['GET','POST'])
@login_required
def edit_process(processo_id):
    from app.clientes.models import Client
    # 1) Carrega o processo existente
    proc = ProcessoService.get(processo_id)
    # 2) Instancia o form com os dados do objeto
    form = ProcessoForm(obj=proc)

    # 3) Injeta todos os query_factories estáticos
    from app.forms.query_factories import usuarios_query, clientes_query
    form.client.query_factory        = clientes_query
    form.case_type.query_factory     = ProcessoService.list_case_types
    form.practice_area.query_factory = ProcessoService.list_practice_areas
    form.court.query_factory         = ProcessoService.list_courts
    form.lead_attorney.query_factory = usuarios_query
    form.co_counsel.query_factory    = usuarios_query
    form.tags.query_factory          = ProcessoService.list_tags

    # 4) Repopula o factory de 'phase' com base no case_type atual
    #    Isto deve vir antes do validate_on_submit!
    if form.case_type.data:
        ct_id = form.case_type.data.id
        form.phase.query_factory = lambda: ProcessoService.list_phases(ct_id)
    else:
        form.phase.query_factory = lambda: []

    # 5) Valida e, se OK, atualiza chamando update(proc, data, user_id)
    if form.validate_on_submit():
        data = {
            'external_id'       : form.external_id.data or None,
            'case_type_id'      : form.case_type.data.id if form.case_type.data else None,
            'phase_id'          : form.phase.data.id if form.phase.data else None,
            'practice_area_id'  : form.practice_area.data.id,
            'court_id'          : form.court.data.id,
            'lead_attorney_id'  : form.lead_attorney.data.id,
            'client_id'         : form.client.data.id,
            'status'            : form.status.data,
            'opposing_party'    : form.opposing_party.data,
            'value_estimate'    : form.value_estimate.data,
            'opened_at'         : form.opened_at.data or datetime.utcnow(),
            'closed_at'         : form.closed_at.data,
            'co_counsel_ids'    : [u.id for u in form.co_counsel.data],
            'tag_ids'           : [t.id for t in form.tags.data],
        }
        ProcessoService.update(proc, data, current_user.id)
        flash('Processo atualizado com sucesso.', 'success')
        return redirect(url_for('processos.detail_process', processo_id=proc.id))

    return render_template(
        'processos/edit.html',
        form=form,
        processo=proc
    )

@processos_bp.route('/<int:processo_id>/delete', methods=['POST'])
@login_required
def delete_process(processo_id):
    from app.prazos.forms import DummyForm
    form = DummyForm()
    if not form.validate_on_submit():
        flash('Falha na validação do formulário (CSRF).', 'danger')
        return redirect(url_for('dashboard_prazos.manage', mode='processos'))

    proc = ProcessoService.get(processo_id)
    if proc is None:
        abort(404)

    ProcessoService.delete(proc)
    flash('Processo excluído com sucesso.', 'success')
    return redirect(url_for('dashboard_prazos.manage', mode='processos'))


@processos_bp.route('/ajax/phases/<int:case_type_id>', methods=['GET'])
#@login_required
def ajax_phases(case_type_id):
    """
    Retorna em JSON as fases associadas a um dado tipo de caso.
    URL: GET /processos/ajax/phases/5
    """
    phases = ProcessoService.list_phases(case_type_id)
    return jsonify([{'id': p.id, 'name': p.name} for p in phases])


@processos_bp.route('/<int:processo_id>/toggle-status', methods=['POST'])
@login_required
def toggle_process_status(processo_id):
    proc = ProcessoService.get(processo_id)
    new_status = ProcessoService.toggle_status(proc, current_user.id)
    flash(f'Status do processo alterado para {new_status}.', 'success')
    return redirect(request.referrer or url_for('processos.list_processes'))


@processos_bp.route('/<int:processo_id>/share', methods=['GET','POST'])
@login_required
def share_process(processo_id):
    proc = ProcessoService.get(processo_id)
    form = ShareProcessForm()

    if form.validate_on_submit():
        # aqui form.users.data já tem o que o usuário selecionou
        ids = [u.id for u in form.users.data]
        ProcessoService.share(proc, ids, current_user.id)
        flash('Compartilhamento atualizado com sucesso.', 'success')
        return redirect(url_for('processos.detail_process', processo_id=proc.id))

    # só no GET (ou em validação falha) é que preenchemos com o que já estava compartilhado
    form.users.data = proc.shared_with.all()

    return render_template(
        'processos/share.html',
        form=form,
        processo=proc
    )

