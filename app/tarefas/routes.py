# app/tarefas/routes.py

from flask import (
    render_template, redirect, url_for,
    flash, request, abort, jsonify, json
)
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from app import db
from app.tarefas import tarefas_bp
from app.tarefas.forms import TarefaForm
from app.extensions import csrf


class DummyForm(FlaskForm):
    """Para CSRF nos formulários de toggle/delete/add_hours."""

@tarefas_bp.route('/<int:assunto_id>/', methods=['GET'])
@login_required
def list_for_assunto(assunto_id):
    from app.tarefas.services import TarefaService
    from app.assuntos.services import AssuntoService

    # 1) Busca o Assunto ou aborta 404
    a = AssuntoService.get_or_404(assunto_id)
    # (opcional) valida permissões
    if not (current_user.id == a.owner_id or current_user in a.shared_with):
        abort(403)

    # 2) Busca as tarefas passando o objeto Assunto
    tarefas = TarefaService.list_for_assunto(a)

    # 3) Instancia o form de CSRF para os botões do dashboard
    csrf_form = DummyForm()

    # 4) Renderiza o dashboard, incluindo csrf_form e o modo correto
    return render_template(
        'dashboard/dashboard.html',
        mode='tarefas',
        # se o template espera listas de assuntos e tarefas:
        assuntos=[a],
        tarefas=tarefas,
        # se existirem agrupamentos ou mapas de horas:
        visible_tasks={},    # ou TarefaService.group_by_assunto([assunto_id])[0]
        task_hours={},       # idem
        # filtros iniciais (ajusta se necessário)
        client_id=None,
        due_date=None,
        status=None,
        sort=None,
        # form de CSRF para os includes
        csrf_form=csrf_form
    )

@tarefas_bp.route('/create/<int:assunto_id>', methods=['GET', 'POST'])
@login_required
def create(assunto_id):
    from app.assuntos.services import AssuntoService
    from app.tarefas.services import TarefaService
    # 1) Busca o Assunto ou aborta 404
    a = AssuntoService.get_or_404(assunto_id)
    # (opcional) valida permissão de acesso ao assunto
    if not (current_user.id == a.owner_id or current_user in a.shared_with):
        abort(403)

    # 2) Instancia tanto o form de dados quanto o DummyForm para CSRF
    form      = TarefaForm()
    csrf_form = DummyForm()

    # 3) Processa submissão
    if form.validate_on_submit():
        data = {
            "title"           : form.title.data,
            "description"     : form.description.data,
            "due_date"        : form.due_date.data,
            "sort_order"      : form.sort_order.data,
            "hours_estimate"  : form.hours_estimate.data,
            "status"          : form.status.data,
            "reminder_offset" : form.reminder_offset.data,
            "recurrence_rule" : form.recurrence_rule.data,
            "shared_with"     : list(form.shared_with.data),
            "calendar_event_id": form.calendar_event_id.data,
            "assunto_id"      : a.id,
        }
        TarefaService.create(data, current_user, a)
        flash('Tarefa criada com sucesso!', 'success')
        return redirect(url_for('tarefas.list_for_assunto', assunto_id=assunto_id))

    # 4) GET: exibe o formulário, passando também o csrf_form e o assunto
    return render_template(
        'tarefas/create.html',
        form=form,
        csrf_form=csrf_form,
        assunto=a
    )

@tarefas_bp.route('/<int:id>/edit', methods=['GET','POST'])
@login_required
def edit(id):
    from app.assuntos.services import AssuntoService
    from app.tarefas.services import TarefaService
    t = TarefaService.get_or_404(id)
    if not (current_user.id==t.owner_id or current_user in t.shared_with):
        abort(403)
    form = TarefaForm(obj=t)
    if form.validate_on_submit():
        data = {
            "title":            form.title.data,
            "description":      form.description.data,
            "due_date":         form.due_date.data,
            "sort_order":       form.sort_order.data,
            "hours_estimate":   form.hours_estimate.data,
            "status":           form.status.data,
            "reminder_offset":  form.reminder_offset.data,
            "recurrence_rule":  form.recurrence_rule.data,
            "shared_with":      list(form.shared_with.data),
            "calendar_event_id":form.calendar_event_id.data
        }
        TarefaService.update(t, data, current_user)
        flash('Tarefa atualizada com sucesso!', 'success')
        return redirect(url_for('tarefas.list_for_assunto', assunto_id=t.assunto_id))
    return render_template('tarefas/edit.html', form=form, tarefa=t)

@tarefas_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    from app.tarefas.services import TarefaService
    form = DummyForm()
    if not form.validate_on_submit():
        flash('Erro de validação (CSRF).', 'danger')
        # Se o CSRF falhar, podemos tentar voltar ao list_for_assunto
        tarefa = TarefaService.get(id)
        return redirect(url_for('tarefas.list_for_assunto', assunto_id=tarefa.assunto_id))

    t = TarefaService.get_or_404(id)
    if not (current_user.id == t.owner_id or current_user in t.shared_with):
        abort(403)

    # Alterna o status da tarefa
    TarefaService.toggle_status(t, current_user)
    flash('Status da tarefa atualizado!', 'success')

    # Tenta ler o próximo destino enviado pelo formulário
    next_url = request.form.get('next')
    if next_url and next_url.startswith('/'):
        # redireciona de volta para a página de onde veio (history, por ex.)
        return redirect(next_url)

    # Se não houver 'next', volta para a listagem padrão de tarefas do assunto
    return redirect(url_for('tarefas.list_for_assunto', assunto_id=t.assunto_id))

@tarefas_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    from app.tarefas.services import TarefaService
    form = DummyForm()
    if not form.validate_on_submit():
        flash('Erro de validação (CSRF).', 'danger')
        return redirect(url_for('tarefas.list_for_assunto', assunto_id=TarefaService.get(id).assunto_id))

    t = TarefaService.get_or_404(id)
    if current_user.id != t.owner_id:
        flash("Permissão negada.", "danger")
    else:
        TarefaService.delete(t, current_user)
        flash('Tarefa excluída com sucesso!', 'success')
    return redirect(url_for('tarefas.list_for_assunto', assunto_id=t.assunto_id))

@tarefas_bp.route('/<int:id>/add_hours', methods=['POST'])
@login_required
def add_hours(id):
    from app.tarefas.services import TarefaService
    from app.tarefas.forms import AddHoursForm
    form = AddHoursForm()
    tarefa = TarefaService.get_or_404(id)
    if form.validate_on_submit():
        TarefaService.add_hours(tarefa,
                                form.horas.data,
                                current_user,
                                form.description.data or None)
        flash("Horas adicionadas com sucesso!", "success")
    else:
        flash("Corrija os erros no formulário.", "danger")
    return redirect(request.referrer or url_for('tarefas.history', id=id))


@tarefas_bp.route('/history/<int:id>', methods=['GET', 'POST'])
@login_required
def history(id):
    import json
    from flask import render_template, flash, redirect, url_for, request, abort
    from flask_login import current_user
    from app.assuntos.services import AssuntoService
    from app.tarefas.models import (
        TarefaHistory,
        TarefaNote,
        TarefaBillingItem,
        NotaHonorarios
    )
    from app.tarefas.forms import (
        NoteForm,
        BillingForm,
        NotaHonorariosForm,
        AddHoursForm
    )
    from app.tarefas.services import TarefaService

    # 1) Carrega tarefa e verifica permissões
    tarefa = TarefaService.get_or_404(id)
    if not (current_user.id == tarefa.owner_id or current_user in tarefa.shared_with):
        abort(403)
    assunto = AssuntoService.get_or_404(tarefa.assunto_id)

    # 2) Instancia os forms
    note_form      = NoteForm(prefix='n')
    billing_form   = BillingForm(prefix='b')
    nota_form      = NotaHonorariosForm(prefix='nh')
    add_hours_form = AddHoursForm()

    # 3) Calcula totais de horas
    total_hours = sum(h.horas_adicionadas for h in tarefa.additions)

    # 4) Itens pendentes para o painel “Para Billing”
    billing_items = TarefaService.list_pending_billing_items(id)
    billed_hours  = sum(item.hours for item in billing_items)

    # 5) Horas pendentes
    pending_hours = max(0, total_hours - billed_hours)

    # 6) Todos os itens enviados (para ✓ no histórico)
    all_billing_items  = TarefaService.list_all_billing_items(id)
    billed_history_ids = {bi.history_id for bi in all_billing_items}

    # === POST handlers ===

    # 7) Adicionar nota de texto
    if note_form.validate_on_submit() and note_form.submit.data:
        TarefaService.add_note(tarefa, note_form.content.data, current_user)
        flash('Nota adicionada!', 'success')
        return redirect(url_for('tarefas.history', id=id))

    # 8) Enviar horas para Billing
    if billing_form.validate_on_submit() and billing_form.submit.data:
        history_id = int(request.form.get('history_id', 0))
        TarefaService.add_billing_item(
            tarefa,
            history_id,
            billing_form.hours.data,
            billing_form.description.data,
            current_user
        )
        flash('Horas enviadas ao Billing!', 'success')
        return redirect(url_for('tarefas.history', id=id))

    # 9) Gerar Nota de Honorários
    if nota_form.validate_on_submit() and nota_form.submit.data:
        nota = TarefaService.gerar_nota_honorarios(tarefa)
        flash(f'Nota de Honorários gerada: #{nota.id}', 'success')
        return redirect(url_for('tarefas.history', id=id))

    # 10) Busca histórico e extrai added_hours
    history_entries = (
        TarefaHistory.query
            .filter_by(tarefa_id=id)
            .order_by(TarefaHistory.changed_at.desc())
            .all()
    )
    for h in history_entries:
        try:
            data = json.loads(h.serialized_data or '{}')
            h.added_hours = float(data.get('added', 0)) if data.get('added') else None
        except Exception:
            h.added_hours = None

    # 11) Notas de texto
    notes = tarefa.notes.order_by(TarefaNote.created_at.desc()).all()

    # 12) Renderiza template com todas as variáveis
    return render_template(
        'tarefas/history.html',
        tarefa               = tarefa,
        assunto              = assunto,
        notes                = notes,
        note_form            = note_form,
        add_hours_form       = add_hours_form,
        billing_form         = billing_form,
        nota_form            = nota_form,
        history              = history_entries,
        billing_items        = billing_items,
        billed_history_ids   = billed_history_ids,
        total_hours          = total_hours,
        billed_hours         = billed_hours,
        pending_hours        = pending_hours
    )




@tarefas_bp.route('/<int:id>/bill', methods=['POST'])
@csrf.exempt
@login_required
def bill_history(id):
    """
    Marca uma entrada de histórico (history_id) como enviada ao Billing.
    Aceita JSON ou form-urlencoded.
    """
    from app.tarefas.services import TarefaService
    from app.tarefas.models   import TarefaHistory

    # tenta JSON primeiro
    data = request.get_json(silent=True) or {}
    # depois form-data
    history_id = data.get('history_id') or request.form.get('history_id')
    if not history_id:
        return jsonify(error="history_id é obrigatório"), 400

    try:
        history_id = int(history_id)
    except ValueError:
        return jsonify(error="history_id inválido"), 400

    tarefa = TarefaService.get_or_404(id)
    if not (current_user.id == tarefa.owner_id or current_user in tarefa.shared_with):
        return jsonify(error="Permissão negada"), 403

    hist = TarefaHistory.query.get_or_404(history_id)

    # extrai horas adicionadas do serialized_data
    import json
    payload = {}
    try:
        payload = json.loads(hist.serialized_data)
    except Exception:
        pass
    hours = float(payload.get('added', 0))

    # cria o billing item
    item = TarefaService.add_billing_item(
        tarefa,
        history_id,
        hours,
        hist.detail,
        current_user
    )

    return jsonify(
        success    = True,
        item_id    = item.id,
        history_id = history_id,
        hours      = item.hours,
        created_at = item.created_at.strftime('%Y-%m-%d %H:%M:%S')
    )


@tarefas_bp.route('/<int:id>/unbill/<int:item_id>', methods=['POST'])
@login_required
def unbill(id, item_id):
    """
    Remove um TarefaBillingItem e redireciona de volta ao history.
    """
    from app.tarefas.services import TarefaService

    tarefa = TarefaService.get_or_404(id)
    if not (current_user.id == tarefa.owner_id or current_user in tarefa.shared_with):
        abort(403)

    TarefaService.remove_billing_item(item_id)
    flash('Item de billing removido.', 'success')
    return redirect(url_for('tarefas.history', id=id))

@tarefas_bp.route('/<int:id>/notas-honorarios', methods=['POST'])
@login_required
def gerar_nota(id):

    from app.tarefas.services import TarefaService
    from app.tarefas.forms import NotaHonorariosForm

    tarefa = TarefaService.get_or_404(id)
    form = NotaHonorariosForm()
    if form.validate_on_submit():
        nota = TarefaService.gerar_nota_honorarios(tarefa)
        flash(f'Nota de Honorários gerada: #{nota.id}', 'success')
    else:
        flash('Não foi possível gerar a nota.', 'danger')
    return redirect(url_for('tarefas.history', id=id))

@tarefas_bp.route('/nota-honorarios/<int:id>', methods=['GET'])
@login_required
def view_nota(id):
    from app.tarefas.models import NotaHonorarios, NotaHonorariosItem
  
    nota = NotaHonorarios.query.get_or_404(id)

    # verifica permissão: só quem é dono da tarefa ou partilhado pode ver
    tarefa = nota.tarefa
    if not (current_user.id == tarefa.owner_id or current_user in tarefa.shared_with):
        abort(403)

    # carrega os items ordenados por data
    items = NotaHonorariosItem.query \
        .filter_by(nota_id=nota.id) \
        .order_by(NotaHonorariosItem.date) \
        .all()

    return render_template(
        'tarefas/view_nota.html',
        nota=nota,
        items=items
    )