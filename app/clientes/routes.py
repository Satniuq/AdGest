# app/clientes/routes.py

import csv, unicodedata, json
from io import StringIO
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, session, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.utils import OFFICE_ROLES
from app.clientes.forms import ClientForm, ShareForm
from app.clientes.forms   import UploadCSVForm
from app.clientes.models import Client, ClientShare
from app.notifications.models import Notification, Comment
from app.notifications.forms import CommentForm
from app.utils import normalize_header
from app.auth.models import User
from app.assuntos.models import Assunto
from app.prazos.models import PrazoJudicial
from app.tarefas.models import TarefaHistory
from app.prazos.models import PrazoHistory
from app.notifications.routes import criar_notificacao  # utilitário de notificações
from app import db

from app.clientes import clientes_bp

from app.clientes import services as client_service

@clientes_bp.route('/', methods=['GET'])
@login_required
def clientes():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    order = request.args.get('order', 'asc')
    prefix = request.args.get('prefix', '').strip()
    nif = request.args.get('nif', '').strip()
    pagination = client_service.list_clients(
        user_id=current_user.id,
        page=page,
        per_page=10,
        search=search,
        order=order,
        prefix=prefix,
        nif=nif,
    )
    return render_template(
        'clientes/clientes.html',
        clients=pagination.items,
        pagination=pagination,
        search=search,
        order=order,
        prefix=prefix,
        nif=nif,
    )


@clientes_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_client():

    current_app.logger.debug(f"[DEBUG] create_client: current_user.role = {current_user.role!r}")

    form = ClientForm()
    form.current_user = current_user
    if form.validate_on_submit():
        is_public = current_user.role in OFFICE_ROLES
        try:
            client_service.create_client(
                user_id=current_user.id,
                name=form.name.data,
                is_public=is_public,
                number_interno=form.number_interno.data,
                nif=form.nif.data,
                address=form.address.data,
                email=form.email.data,
                telephone=form.telephone.data,
                shared_with=form.shared_with.data
            )
            flash("Cliente criado com sucesso!", "success")
            return redirect(url_for('client.clientes'))
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f'Erro de unicidade ao criar cliente: {e}')
            flash("Já existe um cliente com este nome.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao criar cliente: {e}')
            flash(f"Erro ao criar cliente: {e}", "danger")
    return render_template('clientes/create_client.html', form=form)


@clientes_bp.route('/<int:client_id>/delete', methods=['POST'])
@login_required
def delete_client(client_id):
    """
    Exclui um cliente e todo o seu histórico.
    Só permite se o user for owner ou tiver opção 'edit' no compartilhamento.
    """
    # 1. Busca o cliente
    client = Client.query.get(client_id)
    if not client:
        flash("Cliente não encontrado.", "warning")
        return redirect(url_for('client.clientes'))

    # 2. Verifica autorização
    is_owner = client.user_id == current_user.id
    # verifica se há share com opção 'edit'
    shared_edit = client.shares.filter_by(
        user_id=current_user.id, option='edit'
    ).first() is not None

    if not (is_owner or shared_edit):
        flash("Sem permissão para excluir este cliente.", "danger")
        return redirect(url_for('client.clientes'))

    # 3. Tenta apagar via serviço
    try:
        client_service.delete_client(client_id)
        flash("Cliente excluído com sucesso!", "success")
    except ValueError as e:
        # delete_client lança ValueError se não encontrar o cliente
        current_app.logger.error(f"Erro ao excluir cliente: {e}")
        flash(str(e), "warning")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Erro de BD ao excluir cliente: {e}")
        flash("Ocorreu um erro interno ao excluir o cliente.", "danger")

    # 4. Redireciona para a lista de clientes
    return redirect(url_for('client.clientes'))

@clientes_bp.route('/upload_csv', methods=['GET', 'POST'])
@login_required
def upload_client_csv():
    form = UploadCSVForm()
    if form.validate_on_submit():
        try:
            registros = client_service.parse_csv(form.csv_file.data)
            session['client_csv_registros'] = registros
            flash(f"{len(registros)} registros foram lidos com sucesso.", "success")
            return redirect(url_for('client.preview_client_csv'))
        except Exception as e:
            current_app.logger.error(f'Erro ao processar CSV: {e}')
            flash(f"Erro ao processar o arquivo: {e}", "danger")
    return render_template('clientes/upload_client_csv.html', form=form)


@clientes_bp.route('/preview_csv', methods=['GET'])
@login_required
def preview_client_csv():
    # 1) Instancia o form para gerar o csrf_token no template
    form = UploadCSVForm()

    # 2) Carrega os registros guardados na sessão
    registros = session.get('client_csv_registros', [])
    if not registros:
        flash("Nenhum registro para pré-visualizar. Importe um arquivo primeiro.", "warning")
        return redirect(url_for('client.upload_client_csv'))

    # 3) Renderiza a pré-visualização passando o form (para hidden_tag) e os registros
    return render_template(
        'clientes/preview_client_csv.html',
        form=form,
        registros=registros
    )

@clientes_bp.route('/import_confirm', methods=['POST'])
@login_required
def import_confirm():
    registros = session.pop('client_csv_registros', None)
    if not registros:
        flash("Não há registros para importar.", "danger")
        return redirect(url_for('client.upload_client_csv'))
    try:
        count = client_service.import_clients(
            user_id=current_user.id,
            registros=registros
        )
        flash(f"{count} clientes foram importados/atualizados com sucesso!", "success")
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f'Erro de integridade ao importar clientes: {e}')
        flash("Erro de integridade ao importar clientes.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao importar clientes: {e}')
        flash(f"Erro ao importar clientes: {e}", "danger")
    return redirect(url_for('client.clientes'))


@clientes_bp.route('/<int:client_id>', methods=['GET'])
@login_required
def client_info(client_id):
    data = client_service.get_client_history(
        client_id=client_id,
        user_id=current_user.id
    )
    return render_template(
        'clientes/client_info.html',
        **data,
        form=CommentForm(),
        prazo_form=CommentForm()
    )


@clientes_bp.route('/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = client_service.get_client_or_404(client_id, current_user.id)
    form = ClientForm(obj=client)
    form.current_user = current_user
    if form.validate_on_submit():
        is_public = current_user.role in OFFICE_ROLES
        try:
            client_service.update_client(
                client_id=client.id,
                name=form.name.data,
                is_public=is_public,
                number_interno=form.number_interno.data,
                nif=form.nif.data,
                address=form.address.data,
                email=form.email.data,
                telephone=form.telephone.data
            )
            flash("Cliente atualizado com sucesso!", "success")
            return redirect(url_for('client.client_info', client_id=client.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao atualizar cliente: {e}')
            flash(f"Erro ao atualizar cliente: {e}", "danger")
    return render_template('clientes/edit_client.html', form=form, client=client)


@clientes_bp.route('/<int:client_id>/share', methods=['GET', 'POST'])
@login_required
def share_client(client_id):
    client = client_service.get_client_or_404(client_id, current_user.id)
    form = ShareForm()
    if form.validate_on_submit():
        try:
            client_service.share_client(
                client=client,
                shared_users=form.shared_with.data,
                inviter=current_user
            )
            flash("Solicitação de compartilhamento enviada!", "success")
            return redirect(url_for('client.clientes'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao compartilhar cliente: {e}')
            flash(f"Erro ao solicitar compartilhamento: {e}", "danger")
    return render_template('clientes/partilhar_cliente.html', form=form, client=client)



@clientes_bp.route('/<int:client_id>/history', methods=['GET'])
@login_required
def client_history(client_id):
    data = client_service.get_client_history(
        client_id=client_id,
        user_id=current_user.id
    )
    return render_template(
        'clientes/historico.html',
        **data,
        assunto_comment_form=CommentForm(),
        prazo_comment_form=CommentForm(),
        tarefa_comment_form=CommentForm()
    )