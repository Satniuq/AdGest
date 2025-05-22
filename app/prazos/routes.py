# app/prazos/routes.py

import json
from flask import (
    render_template, redirect, url_for,
    flash, request, make_response, jsonify
)
from flask_wtf import FlaskForm
from datetime import datetime
from flask_login import login_required, current_user
from app import db
from app.prazos.models import PrazoHistory
from app.prazos.forms import PrazoJudicialForm, AddPrazoHoursForm, BillingForm, PrazoNotaHonorariosForm
from app.prazos.services import PrazoService
from app.processos.services import ProcessoService
from app.processos.models import ProcessNote
from app.processos.forms import AddNoteForm
from app.prazos.forms import DummyForm

from app.prazos import prazos_bp

class DummyForm(FlaskForm):
    """Formulário vazio apenas para gerar CSRF token"""

@prazos_bp.route('/<int:prazo_id>', methods=['GET', 'POST'])
@login_required
def detail_prazo(prazo_id):
    import json
    from datetime import datetime
    from flask import render_template, flash, redirect, request, url_for
    from flask_login import current_user
    from app import db
    from app.prazos.forms     import BillingForm, PrazoNotaHonorariosForm, AddPrazoHoursForm
    from app.processos.forms  import AddNoteForm
    from app.processos.models import ProcessNote
    from app.prazos.models    import PrazoJudicial, PrazoBillingItem, PrazoNotaHonorarios, PrazoHistory
    from app.prazos.services  import PrazoService

    prazo = PrazoService.get_or_404(prazo_id)

    # 1) Instancia os forms
    add_note_form  = AddNoteForm()
    billing_form   = BillingForm()
    nota_form      = PrazoNotaHonorariosForm()
    add_hours_form = AddPrazoHoursForm()

    # 2) Busca o prazo ou 404 (corrigido)
    prazo = PrazoJudicial.query.get_or_404(prazo_id)

    # 3) Totais de horas
    total_history  = prazo.hours_spent or 0.0
    total_billed   = sum(item.hours for item in prazo.billing_items if not getattr(item, 'invoiced', False))
    unbilled_hours = total_history - total_billed

    # === Tratamento de POSTS ===

    # 4) Adicionar Horas
    if add_hours_form.validate_on_submit() and 'hours' in request.form:
        try:
            hours = add_hours_form.hours.data
            desc  = add_hours_form.description.data or None
            PrazoService.add_hours(prazo, hours, current_user.id, desc)
            flash(f'{hours:.1f}h adicionada(s) com sucesso.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar horas: {e}', 'danger')
        return redirect(request.url)

    # 5) Nova Nota de Processo
    if add_note_form.validate_on_submit() and 'content' in request.form:
        note = ProcessNote(
            processo_id = prazo.processo_id,
            content     = add_note_form.content.data,
            created_at  = datetime.utcnow(),
            created_by  = current_user.id
        )
        db.session.add(note)
        db.session.commit()
        flash('Nota de processo adicionada.', 'success')
        return redirect(request.url)

    # 6) Enviar ao Billing
    if billing_form.validate_on_submit() and 'hours' not in request.form:
        history_id = int(request.form.get('history_id', 0))
        PrazoService.add_billing_item(
            prazo,
            history_id,
            billing_form.hours.data,
            billing_form.description.data,
            current_user.id
        )
        flash('Horas enviadas ao Billing!', 'success')
        return redirect(request.url)

    # === Preparar exibição ===

    # Histórico de processo
    notes = (
        ProcessNote.query
        .filter_by(processo_id=prazo.processo_id)
        .order_by(ProcessNote.created_at.desc())
        .all()
    )

    # Billing items para exibir
    billing_items = PrazoService.list_billing_items(prazo)

    # History IDs já faturados (para ✓ no histórico)
    
    billed_items = (
        PrazoBillingItem.query
            .filter_by(prazo_id=prazo.id)
            .all()
    )
    billed_history_ids = { bi.history_id for bi in billed_items }

    # Notas de Honorários já geradas
    notas_honorarios = (
        PrazoNotaHonorarios.query
        .filter_by(prazo_id=prazo.id)
        .order_by(PrazoNotaHonorarios.created_at.desc())
        .all()
    )

    history_entries = PrazoHistory.query \
        .filter_by(prazo_id=prazo.id) \
        .order_by(PrazoHistory.changed_at.desc()) \
        .all()

    for h in history_entries:
        payload = h.snapshot or {}      # lê direto do JSON field
        h.added_hours = float(payload.get('added', 0))


    # Agora recalcule o total a partir de history_entries
    total_history = sum(h.added_hours for h in history_entries)

    return render_template(
        'detail.html',
        prazo            = prazo,
        notes            = notes,
        add_hours_form   = add_hours_form,
        add_note_form    = add_note_form,
        billing_form     = billing_form,
        nota_form        = nota_form,
        total_history    = total_history,
        total_billed     = total_billed,
        unbilled_hours   = unbilled_hours,
        billing_items    = billing_items,
        billed_history_ids= billed_history_ids,
        history           = history_entries,
        notas_honorarios = notas_honorarios
    )


    
@prazos_bp.route('/processo/<int:processo_id>/create', methods=['GET','POST'])
@login_required
def create_for_processo(processo_id):
    from app.prazos.services import PrazoService
    from app.processos.services import ProcessoService
    from app.clientes.models import Client

    # 1) busca o Processo ou aborta 404
    processo = ProcessoService.get(processo_id)
    if processo is None:
        abort(404)

    # (opcional) validações de permissão:
    # if current_user.id != processo.owner_id:
    #     abort(403)

    # 2) instancia os forms
    form      = PrazoJudicialForm()
    csrf_form = DummyForm()

   # Forçar o client a ser sempre o do processo e torná-lo readonly
    form.client.query_factory = lambda: [processo.client]
    form.client.data          = processo.client
    form.client.render_kw     = {'disabled': True}

    form.deadline_type.query_factory   = PrazoService.list_types
    form.recurrence_rule.query_factory = PrazoService.list_recurrence_rules

    if form.validate_on_submit():
        data = {
            'processo_id'   : processo.id,
            'client_id'     : processo.client.id,
            'type_id'       : form.deadline_type.data.id,
            'recur_rule_id' : form.recurrence_rule.data.id if form.recurrence_rule.data else None,
            'date'          : form.date.data,
            'description'   : form.description.data,
            'comments'      : form.comments.data,
            'hours_spent'   : form.hours_spent.data or 0.0,
            'status'        : form.status.data or 'open'
        }
        PrazoService.create(data, current_user.id)
        flash('Prazo criado com sucesso!', 'success')
        return redirect(url_for('processos.detail_process', processo_id=processo.id))

    return render_template('create_for_processo.html',
                           form=form,
                           processo=processo,
                           csrf_form=csrf_form)


@prazos_bp.route('/<int:prazo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_prazo(prazo_id):
    from app.prazos.services import PrazoService
    from app.processos.services import ProcessoService
    from app.clientes.models import Client
    # 1) busca o Prazo ou 404
    prazo = PrazoService.get(prazo_id)
    if not prazo:
        abort(404)

    # 2) carrega o Processo pai
    processo = ProcessoService.get(prazo.processo_id)
    if not processo:
        abort(404)

    # (opcional) valida permissão:
    # if current_user.id != prazo.owner_id:
    #     abort(403)

    # 3) instancia forms
    form      = PrazoJudicialForm(obj=prazo)
    csrf_form = DummyForm()

    # popula os selects
    form.client.query_factory          = lambda: Client.query.order_by(Client.name).all()
    form.deadline_type.query_factory   = PrazoService.list_types
    form.recurrence_rule.query_factory = PrazoService.list_recurrence_rules

    # 4) POST: aplica alterações
    if form.validate_on_submit():
        data = {
            'processo_id'   : processo.id,
            'client_id'     : form.client.data.id,
            'type_id'       : form.deadline_type.data.id,
            'recur_rule_id' : form.recurrence_rule.data.id if form.recurrence_rule.data else None,
            'date'          : form.date.data,
            'description'   : form.description.data,
            'comments'      : form.comments.data,
            'hours_spent'   : form.hours_spent.data or 0.0,
            'status'        : form.status.data or prazo.status
        }
        PrazoService.update(prazo, data, current_user.id)
        flash('Prazo atualizado com sucesso!', 'success')
        return redirect(url_for('processos.detail_process', processo_id=processo.id))

    # 5) GET: renderiza o form de edição
    return render_template(
        'edit.html',
        processo=processo,
        prazo=prazo,
        form=form,
        csrf_form=csrf_form
    )

@prazos_bp.route('/<int:prazo_id>/delete', methods=['POST'])
@login_required
def delete_prazo(prazo_id):
    """Exclui um prazo judicial."""
    form = DummyForm()
    if form.validate_on_submit():
        prazo = PrazoService.get_or_404(prazo_id)
        PrazoService.delete(prazo)
        flash('Prazo excluído com sucesso.', 'success')
    else:
        flash('Falha na validação do formulário (CSRF).', 'danger')
    return redirect(url_for('dashboard_prazos.manage'))


@prazos_bp.route('/<int:prazo_id>/add_hours', methods=['POST'])
@login_required
def add_hours(prazo_id):
    from app.prazos.forms    import AddPrazoHoursForm
    from app.prazos.services import PrazoService

    prazo = PrazoService.get_or_404(prazo_id)
    form  = AddPrazoHoursForm()

    if form.validate_on_submit():
        horas     = form.hours.data
        desc      = form.description.data or None
        PrazoService.add_hours(prazo,
                               hours     = horas,
                               user_id   = current_user.id,
                               description = desc)  
        flash("Horas adicionadas com sucesso!", "success")
    else:
        flash("Erros no formulário: " +
              "; ".join(f"{f}: {', '.join(errs)}" for f, errs in form.errors.items()),
              "danger")

    # mantém o referrer, voltando à página de detalhe
    ref = form.ref.data or url_for('prazos.detail_prazo', prazo_id=prazo_id)
    return redirect(ref)


@prazos_bp.route('/<int:prazo_id>/toggle-status', methods=['POST'])
@login_required
def toggle_prazo_status(prazo_id):

    prazo = PrazoService.get(prazo_id)
    # alterna entre open e closed
    new_st = PrazoService.toggle_status(prazo)
    flash(f'Status do prazo alterado para {new_st}.', 'success')
    # volta para onde estava
    return redirect(request.referrer or url_for('dashboard_prazos.manage'))


@prazos_bp.route('/<int:prazo_id>/history', methods=['GET'])
@login_required
def prazo_history(prazo_id):
    """Exibe o histórico de alterações de um prazo."""
    prazo   = PrazoService.get(prazo_id)
    history = PrazoService.get_history(prazo_id)
    return render_template(
        'prazos/history.html',
        prazo=prazo,
        history=history
    )

@prazos_bp.route('/<int:prazo_id>/bill', methods=['POST'])
@login_required
def bill_prazo(prazo_id):
    form = BillingForm()
    prazo = PrazoService.get(prazo_id)
    if form.validate_on_submit():
        PrazoService.create_billing_item(
            prazo,
            int(request.form.get('history_id')),
            form.hours.data,
            form.description.data,
            current_user.id
        )

        flash('Horas enviadas ao billing.', 'success')
    else:
        flash('Erro no formulário de billing.', 'danger')
    return redirect(url_for('prazos.detail_prazo', prazo_id=prazo.id))

@prazos_bp.route('/batch-bill', methods=['POST'])
@login_required
def batch_bill():
    ids = request.form.getlist('prazo_ids', type=int)
    descr = request.form.get('description', '')
    for pid in ids:
        p = PrazoService.get(pid)
        if PrazoService.unbilled_hours(p) > 0:
            PrazoService.create_billing_item(
                p, PrazoService.unbilled_hours(p), descr, current_user.id
            )
    flash('Lote faturado.', 'success')
    return redirect(url_for('prazos.detail_prazo'))

from app import csrf

@prazos_bp.route('/<int:prazo_id>/bill_history', methods=['POST'])
@csrf.exempt                # agora funciona de verdade
@login_required
def bill_history(prazo_id):
    history_id = request.form.get('history_id', type=int)
    if not history_id:
        return jsonify(error="history_id é obrigatório"), 400

    # … seu código de criação de item …
    bi = PrazoService.create_billing_item(
        prazo      = PrazoService.get_or_404(prazo_id),
        history_id = history_id,
        hours      = float(PrazoHistory.query.get(history_id).snapshot.get('added', 0)),
        description= PrazoHistory.query.get(history_id).detail,
        user_id    = current_user.id
    )

    return jsonify(
        success    = True,
        item_id    = bi.id,
        history_id = history_id,
        hours      = bi.hours,
        created_at = bi.created_at.strftime('%Y-%m-%d %H:%M:%S')
    )


@prazos_bp.route('/<int:prazo_id>/unbill', methods=['POST'])
@login_required
def unbill(prazo_id):
    from flask import flash, redirect, url_for, request
    from app import db
    from app.prazos.models import PrazoBillingItem
    from app.prazos.services import PrazoService
    from flask_login import current_user

    # opcional: você já tem o CSRFProtect ativo, então o token será verificado automaticamente
    history_id = request.form.get('history_id', type=int)
    if not history_id:
        flash('ID de histórico inválido.', 'warning')
        return redirect(url_for('prazos.detail_prazo', prazo_id=prazo_id))

    item = PrazoBillingItem.query.filter_by(
        prazo_id=prazo_id,
        history_id=history_id
    ).first()

    if item:
        db.session.delete(item)
        db.session.commit()
        flash('Horas revertidas ao histórico.', 'success')
    else:
        flash('Item de billing não encontrado.', 'warning')

    return redirect(url_for('prazos.detail_prazo', prazo_id=prazo_id))

@prazos_bp.route('/<int:prazo_id>/notas-honorarios', methods=['POST'])
@login_required
def gerar_nota(prazo_id):
    from app.prazos.models    import PrazoNotaHonorarios, PrazoNotaHonorariosItem, PrazoJudicial
    from app.prazos.services  import PrazoService
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    # controlas permissões se necessário…
    nota = PrazoService.gerar_nota_honorarios(prazo)
    flash(f'Nota de Honorários gerada: #{nota.id}', 'success')
    return redirect(url_for('prazos.detail_prazo', prazo_id=prazo_id))


@prazos_bp.route('/nota-honorarios/<int:nota_id>', methods=['GET'])
@login_required
def view_nota(nota_id):
    from app.prazos.models    import PrazoNotaHonorarios, PrazoNotaHonorariosItem
    from app.prazos.services  import PrazoService
    nota = PrazoNotaHonorarios.query.get_or_404(nota_id)
    prazo = nota.prazo
    # controlas permissões se necessário…
    items = (
        PrazoNotaHonorariosItem.query
        .filter_by(nota_id=nota.id)
        .order_by(PrazoNotaHonorariosItem.date)
        .all()
    )
    return render_template(
        'view_nota.html',
        nota = nota,
        items= items
    )
