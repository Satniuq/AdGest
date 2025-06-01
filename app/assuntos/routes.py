# app/assuntos/routes.py
from flask import (
    render_template, redirect, url_for,
    flash, request, jsonify, abort, current_app
)
from flask_wtf import FlaskForm
from flask_login import login_required, current_user
from app import db
from app.assuntos import assuntos_bp
from app.assuntos.models import AssuntoNote, AssuntoHistory
from app.assuntos.forms import AssuntoForm, ShareAssuntoForm, NoteForm
from app.assuntos.services import AssuntoService
from app.tarefas.services import TarefaService
from app.tarefas.models import TarefaHistory

class DummyForm(FlaskForm):
    """Formulário vazio apenas para gerar CSRF token"""

@assuntos_bp.route('/', methods=['GET'])
@login_required
def list_assuntos():
    assuntos = AssuntoService.list_for_user(current_user.id)
    from app.assuntos.forms import DummyForm
    csrf_form = DummyForm()
    return render_template(
        'dashboard/dashboard.html',
        assuntos=assuntos,
        csrf_form=csrf_form
    )


@assuntos_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    from app.clientes.models import Client
    form = AssuntoForm()
    if request.method == 'POST':
        current_app.logger.debug(f"Request form data: {dict(request.form)}")
        current_app.logger.debug(f"Form data: {form.data}")
        current_app.logger.debug(f"Raw client_existing: {form.client_existing.data}")
        current_app.logger.debug(f"Request client_existing: {request.form.get('client_existing')}")
        current_app.logger.debug(f"Form errors: {form.errors}")
    
    if form.validate_on_submit():
        client_id = form.client_existing.data
        current_app.logger.debug(f"Client ID from form: {client_id}")
        try:
            client_instance = Client.query.get_or_404(int(client_id))
            data = {
                "title": form.title.data,
                "description": form.description.data,
                "client_existing": client_instance,
                "due_date": form.due_date.data,
            }
            AssuntoService.create(data, current_user)
            flash('Assunto criado com sucesso!', 'success')
            return redirect(url_for('dashboard.dashboard'))
        except ValueError as e:
            current_app.logger.error(f"Erro ao converter client_id: {e}")
            flash('ID do cliente inválido. Por favor, selecione um cliente válido.', 'danger')
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar cliente: {e}")
            flash('Erro ao processar cliente. Tente novamente.', 'danger')
    else:
        current_app.logger.debug(f"Validação falhou, erros: {form.errors}")
    
    return render_template('assuntos/create.html', form=form)   

@assuntos_bp.route('/<int:id>/edit', methods=['GET','POST'])
@login_required
def edit(id):
    a = AssuntoService.get_or_404(id)
    if not (current_user.id==a.owner_id or current_user in a.shared_with):
        abort(403)
    form = AssuntoForm(obj=a)
    # se for GET (primeiro carregamento), pré-seleciona o cliente existente (id!)
    if request.method == 'GET':
        form.client_existing.data = a.client_id

    if form.validate_on_submit():
        data = {
            "title":       form.title.data,
            "description": form.description.data,
            "due_date":    form.due_date.data,
            "client_id":   int(form.client_existing.data),   # usa sempre o id!
        }
        AssuntoService.update(a, data, current_user)
        flash('Assunto atualizado com sucesso!', 'success')
        return redirect(url_for('dashboard.dashboard'))
    return render_template(
        'assuntos/edit.html',
        form=form,
        assunto=a,
        cliente=a.client  # só para mostrar o nome no template
    )


@assuntos_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    from app.assuntos.forms import DummyForm
    form = DummyForm()
    if not form.validate_on_submit():
        flash('Erro de validação CSRF.', 'danger')
        return redirect(url_for('assuntos.list_assuntos'))
    a = AssuntoService.get_or_404(id)
    if not (current_user.id==a.owner_id or current_user in a.shared_with):
        abort(403)
    AssuntoService.toggle_status(a, current_user)
    flash('Status do assunto atualizado!', 'success')
    return redirect(url_for('dashboard.dashboard'))

@assuntos_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    from app.assuntos.forms import DummyForm
    form = DummyForm()
    if not form.validate_on_submit():
        flash('Erro de validação CSRF.', 'danger')
        return redirect(url_for('assuntos.list_assuntos'))
    a = AssuntoService.get_or_404(id)
    if current_user.id != a.owner_id:
        flash("Permissão negada.", "danger")
    else:
        AssuntoService.delete(a, current_user)
        flash('Assunto excluído com sucesso!', 'success')
    return redirect(url_for('dashboard.dashboard'))

@assuntos_bp.route('/update_order', methods=['POST'])
@login_required
def update_order():
    data = request.get_json() or {}
    ordem = data.get('ordem', [])
    try:
        for item in ordem:
            a = AssuntoService.get_or_404(int(item['id']))
            if a.owner_id == current_user.id:
                a.sort_order = int(item['sort_order'])
        db.session.commit()
        return jsonify(status='ok')
    except Exception as e:
        db.session.rollback()
        return jsonify(status='error', message=str(e)), 500

@assuntos_bp.route('/<int:id>/history', methods=['GET', 'POST'])
@login_required
def history(id):
    # 1) Busca o Assunto ou 404
    assunto = AssuntoService.get_or_404(id)

    # 2) Form de nova nota
    form = NoteForm()
    if form.validate_on_submit():
        AssuntoService.add_note(assunto, form.content.data, current_user)
        flash('Nota adicionada!', 'success')
        return redirect(url_for('assuntos.history', id=id))

    # 3) Carrega notas ordenadas
    notes = (
        assunto.notes
               .order_by(AssuntoNote.created_at.desc())
               .all()
    )

    # 4) Carrega tarefas deste Assunto + soma de horas
    visible_tasks_map, hours_map = TarefaService.group_by_assunto([id])
    tarefas = visible_tasks_map.get(id, [])

    # 5) Para cada tarefa, carrega o histórico de horas
    history_map = {
        t.id: t.history.order_by(TarefaHistory.changed_at.desc()).all()
        for t in tarefas
    }

    # 6) Busca o primeiro e o último share
    first_share = (
        AssuntoHistory.query
                      .filter_by(assunto_id=id, change_type='share')
                      .order_by(AssuntoHistory.changed_at.asc())
                      .first()
    )
    last_share = (
        AssuntoHistory.query
                      .filter_by(assunto_id=id, change_type='share')
                      .order_by(AssuntoHistory.changed_at.desc())
                      .first()
    )

    # 7) Renderiza o template com tudo no contexto
    return render_template(
        'assuntos/history_assunto.html',
        assunto=assunto,
        notes=notes,
        add_note_form=form,
        tarefas=tarefas,
        hours_map=hours_map,
        history_map=history_map,
        first_share=first_share,
        last_share=last_share
    )


@assuntos_bp.route('/<int:id>/share', methods=['GET', 'POST'])
@login_required
def share(id):
    a = AssuntoService.get_or_404(id)
    form = ShareAssuntoForm()

    if form.validate_on_submit():
        users = list(form.shared_with.data)
        AssuntoService.share(a, users, current_user)
        flash(f"Assunto '{a.title}' compartilhado com sucesso!", "success")
        return redirect(url_for('assuntos.history', id=id))

    # pré-carrega só no GET (ou em erro de validação)
    form.shared_with.data = a.shared_with.all()
    return render_template('assuntos/share_assunto.html', form=form, assunto=a)