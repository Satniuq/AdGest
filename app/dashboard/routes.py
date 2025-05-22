# app/dashboard/routes.py

from flask import render_template, request, jsonify, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm

from app import db
from app.dashboard import dashboard_bp
from app.assuntos.services import AssuntoService
from app.tarefas.services import TarefaService
from app.clientes.services import list_clients

class DummyForm(FlaskForm):
    """Só para gerar CSRF token no dashboard."""

@dashboard_bp.route('/', methods=['GET'])
@login_required
def dashboard():
    # 1) Parâmetros de modo e filtros via URL
    mode      = request.args.get('mode', 'assuntos')
    client_id = request.args.get('client_id')
    due_date  = request.args.get('due_date')
    status    = request.args.get('status')
    sort      = request.args.get('sort')

    # 2) Dropdown de clientes
    clientes = list_clients(
        user_id=current_user.id,
        page=1,
        per_page=1000
    ).items

    # 3) Instancia o form apenas para gerar o token CSRF
    from flask_wtf import FlaskForm
    class DummyForm(FlaskForm):
        """Só para gerar CSRF token no dashboard."""
    csrf_form = DummyForm()

    if mode == 'assuntos':
        # 3a) Lista de assuntos e soma de horas por assunto
        assuntos, assunto_hours = AssuntoService.list_filtered(
            user_id=current_user.id,
            client_id=client_id,
            due_date=due_date,
            sort=sort
        )
        # 3b) Tarefas agrupadas por assunto + horas por tarefa
        visible_tasks, task_hours = TarefaService.group_by_assunto(
            [a.id for a in assuntos]
        )

        return render_template(
            'dashboard/dashboard.html',
            mode=mode,
            clientes=clientes,
            assuntos=assuntos,
            assunto_hours=assunto_hours,
            visible_tasks=visible_tasks,
            task_hours=task_hours,
            client_id=client_id,
            due_date=due_date,
            sort=sort,
            csrf_form=csrf_form
        )
    else:
        # 4a) Lista de tarefas e soma de horas por tarefa
        tarefas, task_hours = TarefaService.list_filtered(
            user_id=current_user.id,
            client_id=client_id,
            due_date=due_date,
            status=status,
            sort=sort
        )
        # 4b) Lista de assuntos (para usar no botão “Nova Tarefa”)
        assuntos, _ = AssuntoService.list_filtered(
            user_id=current_user.id,
            client_id=client_id,
            due_date=None,
            sort='asc'
        )

        return render_template(
            'dashboard/dashboard.html',
            mode=mode,
            clientes=clientes,
            tarefas=tarefas,
            task_hours=task_hours,
            assuntos=assuntos,
            client_id=client_id,
            due_date=due_date,
            status=status,
            sort=sort,
            csrf_form=csrf_form
        )


@dashboard_bp.route('/update_order', methods=['POST'])
@login_required
def update_order():
    """
    Recebe JSON { order: [<assunto_id>, ...] }
    e atualiza o sort_order de cada Assunto para o usuário atual.
    """
    data = request.get_json() or {}
    order = data.get('order', [])
    # Atualiza cada Assunto
    for idx, assunto_id in enumerate(order):
        a = AssuntoService.get_or_404(assunto_id)
        if a.owner_id != current_user.id:
            abort(403)
        a.sort_order = idx
    db.session.commit()
    return jsonify(success=True)

