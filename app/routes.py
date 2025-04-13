#BEGIN IMPORT
import csv
import unicodedata
from io import StringIO
import json
import os
#END IMPORT

#BEGIN FROM
# Bibliotecas padrão
from datetime import datetime, date, timedelta
# Bibliotecas de terceiros
from flask import Blueprint, json, render_template, redirect, url_for, flash, request, current_app, session, jsonify
from sqlalchemy import func, or_, and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user

# Módulos do projeto
from app.forms import (RegistrationForm, LoginForm, AssuntoForm, TarefaForm, 
                       PrazoJudicialForm, ClientForm, ShareForm, CommentForm,
                       EditProfileForm, RequestResetForm, ResetPasswordForm)
from app.models import (User, Assunto, Tarefa, PrazoJudicial, db, Client,
                        NotaHonorarios, ClientShare, shared_assuntos,
                        shared_prazos, HoraAdicao, DocumentoContabilistico,
                        Notification, AssuntoHistory, TarefaHistory, PrazoHistory,
                        Comment)
from app.decorators import admin_required
from app.decorators import handle_db_errors
from app import db
from app.gcs_helpers import upload_to_gcs
#END FROM

#BEGIN DEF
def normalize_header(header):
    header = header.strip().lower()
    header = unicodedata.normalize('NFKD', header).encode('ASCII', 'ignore').decode('utf-8')
    return header

main = Blueprint('main', __name__)
#END DEF

#BEGIN ROTAS DE AUTENTICAÇÃO

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@main.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        current_user.nickname = form.nickname.data
        current_user.email = form.email.data

        if form.profile_image.data:
            file_data = form.profile_image.data
            current_app.logger.info(f"Tipo de form.profile_image.data: {type(file_data)}")
            current_app.logger.info(f"Arquivo recebido: {repr(file_data)}")
            if hasattr(file_data, 'filename') and file_data.filename:
                filename = secure_filename(file_data.filename)
                current_app.logger.info(f"Fazendo upload da imagem '{filename}' para o GCS")
                try:
                    # Usa a função de upload para o GCS
                    public_url = upload_to_gcs(
                        file_obj=file_data,
                        filename=filename,
                        content_type=file_data.content_type
                    )
                    # Atualiza o atributo do usuário com a URL da imagem
                    current_user.profile_image = public_url
                except Exception as e:
                    current_app.logger.error(f"Erro ao fazer upload para o GCS: {e}")
                    flash("Erro ao fazer upload da imagem. Tente novamente.", "danger")
                    return redirect(url_for("main.edit_profile"))
            else:
                current_app.logger.info("Nenhum arquivo selecionado ou o valor não é um objeto FileStorage.")
        else:
            current_app.logger.info("Campo profile_image está vazio.")

        try:
            db.session.commit()
            flash('Perfil atualizado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar o perfil. Tente novamente.', 'danger')
            current_app.logger.error(f"Erro ao atualizar perfil: {e}")
        
        return redirect(url_for('main.profile'))

    return render_template('edit_profile.html', form=form)


@main.route('/register', methods=['GET', 'POST'])
@login_required
@admin_required
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            nickname=form.nickname.data,
            email=form.email.data,
            password=hashed_password,
            role=form.role.data  # O papel é definido conforme a seleção do admin
        )
        db.session.add(user)
        try:
            db.session.commit()
            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('main.index'))
        except IntegrityError:
            db.session.rollback()
            flash('O nome de usuário já está em uso. Por favor, escolha outro.', 'danger')
    else:
        # Se houver erros, podemos flashá-los ou exibi-los no template
        if form.errors:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Erro no campo {field}: {error}", 'danger')
    return render_template('register.html', form=form)


@main.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')
    return render_template('login.html', form=form)

@main.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)  # Função que envia o e-mail
        flash('Se um usuário com esse e-mail existir, as instruções para redefinir a senha foram enviadas.', 'info')
        return redirect(url_for('main.login'))
    return render_template('reset_request.html', form=form)

@main.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('O token é inválido ou expirou.', 'warning')
        return redirect(url_for('main.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.password.data)
        db.session.commit()
        flash('Sua senha foi atualizada! Faça login com a nova senha.', 'success')
        return redirect(url_for('main.login'))
    return render_template('reset_token.html', form=form)

from flask_mail import Message
from app import mail

def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for('main.reset_token', token=token, _external=True)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@seusite.com')
    msg = Message('Redefinir senha - AdGest',
                  sender=sender,
                  recipients=[user.email])
    msg.body = f'''Para redefinir sua senha, visite o seguinte link:
{reset_url}

Se você não solicitou essa alteração, ignore este e-mail.
'''
    mail.send(msg)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Saiu do sistema.', 'info')
    return redirect(url_for('main.login'))
#END ROTAS DE AUTENTICAÇÃO

#BEGIN ROTA INDEX
### PAGINA PRINCIPAL – EXIBE SO NOME DO PROGRAMA E INFOS EMPRESA DEPOIS
@main.route('/')
@login_required
def index():
    # Exibe somente o nome do programa
    return render_template('index.html')
#END ROTA INDEX

#BEGIN ROTAS ASSUNTOS, TAREFAS E PRAZOS

@main.route('/dashboard')
@login_required
def dashboard():
    # Carrega TODOS os assuntos do usuário ou compartilhados
    all_assuntos = Assunto.query.filter(
        or_(
            Assunto.user_id == current_user.id,
            Assunto.shared_with.any(id=current_user.id)
        )
    ).order_by(Assunto.sort_order, Assunto.nome_assunto).all()

    # Filtra para exibir:
    # - Assuntos que não estão concluídos (is_completed == False)
    # ou
    # - Assuntos concluídos mas que possuem pelo menos uma tarefa que não está concluída
    assuntos = []
    for assunto in all_assuntos:
        if not assunto.is_completed:
            assuntos.append(assunto)
        else:
            # Se estiver concluído, verifica se existe pelo menos uma tarefa aberta
            if any(not tarefa.is_completed for tarefa in assunto.tarefas):
                assuntos.append(assunto)

    # Cria o dicionário para as tarefas visíveis para cada assunto
    assuntos_tarefas_visiveis = {}
    for assunto in assuntos:
        if assunto.shared_with.count() > 0:
            tarefas_visiveis = assunto.tarefas
        else:
            tarefas_visiveis = [tarefa for tarefa in assunto.tarefas if tarefa.user_id == current_user.id]
        assuntos_tarefas_visiveis[assunto.id] = tarefas_visiveis

    # Busca prazos pendentes (de acordo com sua lógica já existente)
    prazos = PrazoJudicial.query.filter(
        or_(
            PrazoJudicial.user_id == current_user.id,
            PrazoJudicial.shared_with.any(id=current_user.id)
        ),
        PrazoJudicial.status == False
    ).order_by(PrazoJudicial.prazo).all()

    current_date = date.today()
    tomorrow_date = current_date + timedelta(days=1)

    return render_template(
        'dashboard.html',
        assuntos=assuntos,
        assuntos_tarefas_visiveis=assuntos_tarefas_visiveis,
        prazos=prazos,
        current_date=current_date,
        tomorrow_date=tomorrow_date
    )

### ROTAS PARA ASSUNTOS, TAREFAS E PRAZOS (já existentes) ###
@main.route('/assunto/create', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def create_assunto():
    form = AssuntoForm()
    if form.validate_on_submit():
        try:
            if form.client_existing.data:
                client_id = form.client_existing.data.id
            else:
                new_client = Client(
                    user_id=current_user.id,
                    name=form.client_new.data.strip()
                )
                db.session.add(new_client)
                db.session.commit()
                client_id = new_client.id
            novo = Assunto(
                user_id=current_user.id,
                client_id=client_id,
                nome_assunto=form.nome_assunto.data,
                due_date=form.due_date.data,
                sort_order=form.sort_order.data or 0
            )
            db.session.add(novo)
            db.session.commit()

            # LOG de histórico
            hist = AssuntoHistory(
                assunto_id=novo.id,
                change_type='created',
                changed_at=datetime.utcnow(),
                changed_by=current_user.id,
                snapshot=json.dumps({
                    'nome_assunto': novo.nome_assunto,
                    'due_date': str(novo.due_date) if novo.due_date else None,
                    'sort_order': novo.sort_order
                    # inclua o que julgar útil
                })
            )
            db.session.add(hist)
            db.session.commit()
            flash('Assunto criado com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))
        except IntegrityError as e:
            db.session.rollback()
            if "UNIQUE constraint failed: clients.name" in str(e.orig):
                flash("Erro: O nome do cliente já está registrado. Por favor, escolha outro nome.", 'danger')
            else:
                flash(f"Erro ao criar assunto: {str(e)}", 'danger')
            current_app.logger.error(f'Erro ao criar assunto: {str(e)}')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao criar assunto: {str(e)}')
            flash(f'Erro ao criar assunto: {str(e)}', 'danger')
    return render_template('create_assunto.html', form=form)

@main.route('/assunto/edit/<int:assunto_id>', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def edit_assunto(assunto_id):
    assunto = Assunto.query.get_or_404(assunto_id)
    form = AssuntoForm(obj=assunto)
    form.client_existing.query = Client.query
    form.client_existing.data = assunto.client

    if form.validate_on_submit():
        try:
            # Capture os dados antigos
            old_data = {
                'nome_assunto': assunto.nome_assunto,
                'due_date': assunto.due_date.isoformat() if assunto.due_date else None,
                'sort_order': assunto.sort_order,
                'client_id': assunto.client_id
            }
            
            # Atualiza os dados
            assunto.nome_assunto = form.nome_assunto.data
            assunto.due_date = form.due_date.data
            assunto.sort_order = form.sort_order.data or 0
            if form.client_existing.data:
                assunto.client_id = form.client_existing.data.id
            else:
                new_client = Client(
                    user_id=current_user.id,
                    name=form.client_new.data.strip()
                )
                db.session.add(new_client)
                db.session.commit()
                assunto.client_id = new_client.id
            db.session.commit()
            
            # Capture os dados novos
            new_data = {
                'nome_assunto': assunto.nome_assunto,
                'due_date': assunto.due_date.isoformat() if assunto.due_date else None,
                'sort_order': assunto.sort_order,
                'client_id': assunto.client_id
            }
            
            # Calcule as diferenças
            diff = {}
            for key in old_data:
                if old_data[key] != new_data[key]:
                    diff[key] = {'old': old_data[key], 'new': new_data[key]}
            
            # Registre o histórico, se houver diferenças
            if diff:
                import json
                hist = AssuntoHistory(
                    assunto_id=assunto.id,
                    change_type='editado',
                    changed_by=current_user.id,
                    snapshot=json.dumps(diff)
                )
                db.session.add(hist)
                db.session.commit()
            
            # Notificações para os envolvidos
            envolvidos = set()
            envolvidos.add(assunto.user)
            envolvidos.update(assunto.shared_with)
            for user in envolvidos:
                if user.id != current_user.id:
                    mensagem = f"{current_user.nickname} editou o assunto '{assunto.nome_assunto}'."
                    link = url_for('main.assunto_info', assunto_id=assunto.id) if 'assunto_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                    criar_notificacao(user.id, "update", mensagem, link)
            
            flash('Assunto atualizado com sucesso e histórico registrado!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao atualizar assunto: {str(e)}')
            flash(f'Erro ao atualizar assunto: {str(e)}', 'danger')
            return render_template('edit_assunto.html', form=form, assunto=assunto)
    
    return render_template('edit_assunto.html', form=form, assunto=assunto)


@main.route('/assunto/delete/<int:assunto_id>', methods=['POST'])
@login_required
def delete_assunto(assunto_id):
    assunto = Assunto.query.get_or_404(assunto_id)
    if assunto.user_id != current_user.id:
        flash("Não pode excluir assuntos de outros usuários.", "danger")
        return redirect(url_for('main.dashboard'))
    try:
        # Armazena a lista de usuários compartilhados antes de deletar
        shared_users = list(assunto.shared_with)
        db.session.execute(
            shared_assuntos.delete().where(shared_assuntos.c.assunto_id == assunto.id)
        )
        db.session.delete(assunto)
        db.session.commit()
        flash('Assunto excluído com sucesso!', 'success')

        for user in shared_users:
            if user.id != current_user.id:
                mensagem = f"{current_user.nickname} excluiu o assunto '{assunto.nome_assunto}'."
                criar_notificacao(user.id, "update", mensagem)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao excluir assunto: {str(e)}')
        flash(f'Erro ao excluir assunto: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))

@main.route('/assunto/toggle_status/<int:assunto_id>', methods=['POST'])
@login_required
def toggle_status_assunto(assunto_id):
    assunto = Assunto.query.get_or_404(assunto_id)
    try:
        assunto.is_completed = not assunto.is_completed
        if assunto.is_completed:
            assunto.data_conclusao = datetime.utcnow().date()
            assunto.completed_by = current_user.id
            acao = "concluído"
            # Marca todas as tarefas como concluídas também
            for tarefa in assunto.tarefas:
                tarefa.is_completed = True
                tarefa.data_conclusao = datetime.utcnow().date()
                tarefa.completed_by = current_user.id
        else:
            assunto.data_conclusao = None
            assunto.completed_by = None
            acao = "reaberto"
        db.session.commit()
        flash('Status do assunto atualizado!', 'success')
        
        # Notifica os envolvidos (criador e usuários partilhados, exceto o atual)
        envolvidos = set()
        envolvidos.add(assunto.user)
        envolvidos.update(assunto.shared_with.all() if hasattr(assunto.shared_with, 'all') else assunto.shared_with)
        for user in envolvidos:
            if user.id != current_user.id:
                mensagem = f"{current_user.nickname} marcou o assunto '{assunto.nome_assunto}' como {acao}."
                link = url_for('main.assunto_info', assunto_id=assunto.id) if 'assunto_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                criar_notificacao(user.id, "update", mensagem, link)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao alterar status do assunto: {str(e)}')
        flash(f'Erro ao alterar status do assunto: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))


@main.route('/tarefa/create/<int:assunto_id>', methods=['GET', 'POST'])
@login_required
def create_tarefa(assunto_id):
    assunto = Assunto.query.get_or_404(assunto_id)
    form = TarefaForm()
    if form.validate_on_submit():
        try:
            nova = Tarefa(
                user_id=current_user.id,
                assunto_id=assunto.id,
                nome_tarefa=form.nome_tarefa.data,
                descricao=form.descricao.data or '',
                due_date=form.due_date.data,
                sort_order=form.sort_order.data or 0,
                horas=form.horas.data or 0.0,
                is_completed=False
            )
            db.session.add(nova)
            db.session.commit()

            # Registra o histórico da criação
            hist = TarefaHistory(
                tarefa_id=nova.id,
                change_type='criada',
                changed_at=datetime.utcnow(),
                changed_by=current_user.id,
                snapshot=json.dumps({
                    'nome_tarefa': nova.nome_tarefa,
                    'descricao': nova.descricao,
                    'due_date': str(nova.due_date) if nova.due_date else None,
                    'sort_order': nova.sort_order,
                    'horas': nova.horas,
                    'is_completed': nova.is_completed
                })
            )
            db.session.add(hist)
            db.session.commit()

            flash('Tarefa criada com sucesso!', 'success')
            # Define o conjunto de usuários envolvidos:
            # Inclui o criador do assunto e todos os usuários compartilhados.
            envolvidos = set()
            envolvidos.add(assunto.user)
            envolvidos.update(assunto.shared_with)
            
            # Envia notificação para todos os envolvidos, exceto quem criou a tarefa.
            for user in envolvidos:
                if user.id != current_user.id:
                    mensagem = f"{current_user.nickname} criou a nova tarefa '{nova.nome_tarefa}' no assunto '{assunto.nome_assunto}'."
                    link = url_for('main.tarefa_info', tarefa_id=nova.id) if 'tarefa_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                    criar_notificacao(user.id, "update", mensagem, link)
            
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao criar tarefa: {str(e)}')
            flash(f'Erro ao criar tarefa: {str(e)}', 'danger')
    return render_template('create_tarefa.html', form=form, assunto=assunto)

@main.route('/tarefa/edit/<int:tarefa_id>', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def edit_tarefa(tarefa_id):
    tarefa = Tarefa.query.get_or_404(tarefa_id)
    form = TarefaForm(obj=tarefa)
    if form.validate_on_submit():
        try:
            # Captura os dados antigos
            old_data = {
                'nome_tarefa': tarefa.nome_tarefa,
                'descricao': tarefa.descricao,
                'due_date': tarefa.due_date.isoformat() if tarefa.due_date else None,
                'sort_order': tarefa.sort_order,
                'horas': tarefa.horas,
                'is_completed': tarefa.is_completed
            }
            
            # Atualiza os dados
            tarefa.nome_tarefa = form.nome_tarefa.data
            tarefa.descricao = form.descricao.data
            tarefa.due_date = form.due_date.data
            tarefa.sort_order = form.sort_order.data or 0
            tarefa.horas = form.horas.data or 0.0
            db.session.commit()
            
            # Captura os dados novos e calcula as diferenças
            new_data = {
                'nome_tarefa': tarefa.nome_tarefa,
                'descricao': tarefa.descricao,
                'due_date': tarefa.due_date.isoformat() if tarefa.due_date else None,
                'sort_order': tarefa.sort_order,
                'horas': tarefa.horas,
                'is_completed': tarefa.is_completed
            }
            
            diff = {}
            for key in old_data:
                if old_data[key] != new_data[key]:
                    diff[key] = {'old': old_data[key], 'new': new_data[key]}
            
            # Registra o histórico se houver alterações
            if diff:
                hist = TarefaHistory(
                    tarefa_id=tarefa.id,
                    change_type='editada',
                    changed_at=datetime.utcnow(),
                    changed_by=current_user.id,
                    snapshot=json.dumps(diff)
                )
                db.session.add(hist)
                db.session.commit()
            
            flash('Tarefa atualizada com sucesso!', 'success')
            
            # Notifica os usuários envolvidos
            envolvidos = set()
            envolvidos.add(tarefa.user)
            envolvidos.update(tarefa.assunto.shared_with)
            for user in envolvidos:
                if user.id != current_user.id:
                    mensagem = f"{current_user.nickname} editou a tarefa '{tarefa.nome_tarefa}'."
                    link = url_for('main.tarefa_info', tarefa_id=tarefa.id) if 'tarefa_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                    criar_notificacao(user.id, "update", mensagem, link)
                    
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao atualizar tarefa: {str(e)}')
            flash(f'Erro ao atualizar tarefa: {str(e)}', 'danger')
    return render_template('edit_tarefa.html', form=form, tarefa=tarefa)


@main.route('/tarefa/delete/<int:tarefa_id>', methods=['POST'])
@login_required
def delete_tarefa(tarefa_id):
    tarefa = Tarefa.query.get_or_404(tarefa_id)
    if tarefa.user_id != current_user.id:
        flash("Não pode excluir tarefas de outros usuários.", "danger")
        return redirect(url_for('main.dashboard'))
    # Notifica os usuários antes da exclusão
    for user in tarefa.assunto.shared_with:
        if user.id != current_user.id:
            mensagem = f"{current_user.nickname} excluiu a tarefa '{tarefa.nome_tarefa}'."
            criar_notificacao(user.id, "update", mensagem)
    try:
        db.session.delete(tarefa)
        db.session.commit()
        flash('Tarefa excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao excluir tarefa: {str(e)}')
        flash(f'Erro ao excluir tarefa: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))

@main.route('/tarefa/add_hours/<int:tarefa_id>', methods=['POST'])
@login_required
def add_hours_tarefa(tarefa_id):
    tarefa = Tarefa.query.get_or_404(tarefa_id)
    try:
        horas = float(request.form.get('horas', 0))
        tarefa.horas += horas
        registro = HoraAdicao(
            item_type='tarefa',
            item_id=tarefa.id,
            horas_adicionadas=horas,
            user_id=current_user.id
        )
        db.session.add(registro)
        db.session.commit()

        # Registra no histórico que horas foram adicionadas
        hist = TarefaHistory(
            tarefa_id=tarefa.id,
            change_type='horas_adicionadas',
            changed_at=datetime.utcnow(),
            changed_by=current_user.id,
            snapshot=json.dumps({'horas_adicionadas': horas, 'total_horas': tarefa.horas})
        )
        db.session.add(hist)
        db.session.commit()

        flash("Horas adicionadas com sucesso!", "success")
        # Cria um conjunto para unificar os usuários a serem notificados
        notificados = set()
        # Adiciona os usuários compartilhados no assunto
        assunto_users = tarefa.assunto.shared_with.all() if hasattr(tarefa.assunto.shared_with, 'all') else tarefa.assunto.shared_with
        for user in assunto_users:
            notificados.add(user)
        # Além disso, inclua o criador do assunto, se não for o usuário atual
        if tarefa.assunto.user_id != current_user.id:
            # Obtenha o usuário criador do assunto (ADM)
            notificados.add(tarefa.assunto.user)
        
        # Remova o usuário que está adicionando as horas (ADV)
        notificados = [user for user in notificados if user.id != current_user.id]

        for user in notificados:
            mensagem = f"{current_user.nickname} adicionou {horas}h na tarefa '{tarefa.nome_tarefa}'."
            link = url_for('main.tarefa_info', tarefa_id=tarefa.id) if 'tarefa_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
            criar_notificacao(user.id, "update", mensagem, link)
                
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao adicionar horas: {str(e)}", "danger")
    return redirect(url_for('main.dashboard'))


@main.route('/tarefa/toggle_status/<int:tarefa_id>', methods=['POST'])
@login_required
def toggle_status_tarefa(tarefa_id):
    tarefa = Tarefa.query.get_or_404(tarefa_id)
    try:
        tarefa.is_completed = not tarefa.is_completed
        if tarefa.is_completed:
            tarefa.data_conclusao = datetime.utcnow().date()
            tarefa.completed_by = current_user.id
            acao = "concluída"
        else:
            tarefa.data_conclusao = None
            tarefa.completed_by = None
            acao = "reaberta"
        db.session.commit()

        # Registra a mudança de status no histórico
        hist = TarefaHistory(
            tarefa_id=tarefa.id,
            change_type='status_alterado',
            changed_at=datetime.utcnow(),
            changed_by=current_user.id,
            snapshot=json.dumps({'novo_status': acao})
        )
        db.session.add(hist)
        db.session.commit()

        flash('Status da tarefa atualizado!', 'success')
        notificados = set()
        # Adiciona os usuários compartilhados do assunto
        assunto_users = tarefa.assunto.shared_with.all() if hasattr(tarefa.assunto.shared_with, 'all') else tarefa.assunto.shared_with
        for user in assunto_users:
            notificados.add(user)
        # Adiciona o dono do assunto
        notificados.add(tarefa.assunto.user)
        # Remove o usuário que executou a ação
        notificados = [user for user in notificados if user.id != current_user.id]
        
        for user in notificados:
            mensagem = f"{current_user.nickname} marcou a tarefa '{tarefa.nome_tarefa}' como {acao}."
            link = url_for('main.tarefa_info', tarefa_id=tarefa.id) if 'tarefa_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
            criar_notificacao(user.id, "update", mensagem, link)
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao alterar status da tarefa: {str(e)}')
        flash(f'Erro ao alterar status da tarefa: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))


@main.route('/prazos/create', methods=['GET', 'POST'])
@login_required
def create_prazo():
    form = PrazoJudicialForm()
    if form.is_submitted() and not form.validate():
        print("Erros do formulário de prazo:", form.errors)
    if form.validate_on_submit():
        try:
            if form.client_existing.data:
                client_id = form.client_existing.data.id
            else:
                new_client = Client(
                    user_id=current_user.id,  # Adicionado aqui
                    name=form.client_new.data.strip()
                 )
                db.session.add(new_client)
                db.session.commit()
                client_id = new_client.id
            novo = PrazoJudicial(
                user_id=current_user.id,
                client_id=client_id,
                assunto=form.assunto.data,
                processo=form.processo.data,
                prazo=form.prazo.data,
                comentarios=form.comentarios.data or ''
            )
            if form.shared_with.data:
                novo.shared_with = form.shared_with.data

            db.session.add(novo)
            db.session.commit()
            flash('Prazo criado com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))
        except IntegrityError as e:
            db.session.rollback()
            # Verifica se o erro se refere à constraint UNIQUE do nome do cliente
            if "UNIQUE constraint failed: clients.name" in str(e.orig):
                flash("Erro: O nome do cliente já está registrado. Por favor, escolha outro nome.", 'danger')
            else:
                flash(f"Erro ao criar prazo: {str(e)}", 'danger')
            current_app.logger.error(f'Erro ao criar prazo: {str(e)}')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao criar prazo: {str(e)}')
            flash(f'Erro ao criar prazo: {str(e)}', 'danger')
    return render_template('prazos_judiciais.html', form=form)

@main.route('/prazo/edit/<int:prazo_id>', methods=['GET', 'POST'])
@login_required
def edit_prazo(prazo_id):
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    old_shared = list(prazo.shared_with)  # Se necessário para comparação ou notificações
    form = PrazoJudicialForm(obj=prazo)
    form.client_existing.query = Client.query
    form.client_existing.data = prazo.client
    if form.validate_on_submit():
        try:
            # Capture os dados antigos
            old_data = {
                'assunto': prazo.assunto,
                'processo': prazo.processo,
                'prazo': prazo.prazo.isoformat() if prazo.prazo else None,
                'comentarios': prazo.comentarios,
                'horas': prazo.horas,
                'client_id': prazo.client_id,
            }
            
            # Atualiza os dados
            if form.client_existing.data:
                prazo.client_id = form.client_existing.data.id
            else:
                new_client = Client(
                    user_id=current_user.id,
                    name=form.client_new.data.strip()
                )
                db.session.add(new_client)
                db.session.commit()
                prazo.client_id = new_client.id

            prazo.assunto = form.assunto.data
            prazo.processo = form.processo.data
            prazo.prazo = form.prazo.data
            prazo.comentarios = form.comentarios.data or ''
            
            # Atualiza o compartilhamento sem remover os já existentes
            if current_user.id == prazo.user_id:
                # Se o editor é o criador, preserva os compartilhamentos já existentes e adiciona os novos
                prazo.shared_with = list(set(prazo.shared_with).union(set(form.shared_with.data)))
            else:
                # Se o editor não é o criador, utiliza os dados do formulário,
                # mas garante que o próprio usuário que está editando continue na partilha
                prazo.shared_with = form.shared_with.data
                if current_user not in prazo.shared_with:
                    prazo.shared_with.append(current_user)
            
            prazo.horas = form.horas.data or 0.0
            db.session.commit()
            flash('Prazo atualizado com sucesso!', 'success')

            # Capture os dados novos
            new_data = {
                'assunto': prazo.assunto,
                'processo': prazo.processo,
                'prazo': prazo.prazo.isoformat() if prazo.prazo else None,
                'comentarios': prazo.comentarios,
                'horas': prazo.horas,
                'client_id': prazo.client_id,
            }
            
            # Calcule as diferenças e registre no histórico, se houver alterações
            diff = {}
            for key in old_data:
                if old_data[key] != new_data[key]:
                    diff[key] = {'old': old_data[key], 'new': new_data[key]}
            
            if diff:
                import json
                hist = PrazoHistory(
                    prazo_id=prazo.id,
                    change_type='editado',
                    changed_by=current_user.id,
                    snapshot=json.dumps(diff)
                )
                db.session.add(hist)
                db.session.commit()
            
            # Notifica todos os envolvidos: criador + usuários compartilhados
            envolvidos = set()
            envolvidos.add(prazo.user)
            envolvidos.update(prazo.shared_with)
            for user in envolvidos:
                if user.id != current_user.id:
                    mensagem = f"{current_user.nickname} editou o prazo '{prazo.assunto}' (Processo: {prazo.processo})."
                    link = url_for('main.prazo_info', prazo_id=prazo.id) if 'prazo_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                    criar_notificacao(user.id, "update", mensagem, link)
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao atualizar prazo: {str(e)}')
            flash(f'Erro ao atualizar prazo: {str(e)}', 'danger')
    return render_template('edit_prazo.html', form=form, prazo=prazo)


@main.route('/prazo/delete/<int:prazo_id>', methods=['POST'])
@login_required
def delete_prazo(prazo_id):
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    if prazo.user_id != current_user.id:
        flash("Não pode excluir prazos de outros usuários.", "danger")
        return redirect(url_for('main.dashboard'))
    try:
        # Armazena os usuários compartilhados antes de deletar
        shared_users = list(prazo.shared_with)
        db.session.execute(
            shared_prazos.delete().where(shared_prazos.c.prazo_id == prazo.id)
        )
        db.session.delete(prazo)
        db.session.commit()
        flash('Prazo excluído com sucesso!', 'success')

        for user in shared_users:
            if user.id != current_user.id:
                mensagem = f"{current_user.nickname} excluiu o prazo '{prazo.assunto}' (Processo: {prazo.processo})."
                criar_notificacao(user.id, "update", mensagem)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao excluir prazo: {str(e)}')
        flash(f'Erro ao excluir prazo: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))

@main.route('/prazo/add_hours/<int:prazo_id>', methods=['POST'])
@login_required
def add_hours_prazo(prazo_id):
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    try:
        horas = float(request.form.get('horas', 0))
        prazo.horas += horas
        
        registro = HoraAdicao(
            item_type='prazo',
            item_id=prazo.id,
            horas_adicionadas=horas,
            user_id=current_user.id
        )
        db.session.add(registro)
        db.session.commit()
        flash("Horas adicionadas com sucesso!", "success")
        
        # Notifica os envolvidos
        notificados = set()
        prazo_users = prazo.shared_with.all() if hasattr(prazo.shared_with, 'all') else prazo.shared_with
        for user in prazo_users:
            notificados.add(user)
        if prazo.user_id != current_user.id:
            notificados.add(prazo.user)
        notificados = [user for user in notificados if user.id != current_user.id]
        for user in notificados:
            mensagem = f"{current_user.nickname} adicionou {horas}h ao prazo '{prazo.assunto}' (Processo: {prazo.processo})."
            link = url_for('main.prazo_info', prazo_id=prazo.id) if 'prazo_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
            criar_notificacao(user.id, "update", mensagem, link)
        
        # Registra o histórico da adição de horas
        import json
        diff = {'horas': {'old': prazo.horas - horas, 'new': prazo.horas}}
        hist = PrazoHistory(
            prazo_id=prazo.id,
            change_type='horas_adicionadas',
            changed_by=current_user.id,
            snapshot=json.dumps(diff)
        )
        db.session.add(hist)
        db.session.commit()
                
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao adicionar horas: {str(e)}", "danger")
    return redirect(url_for('main.dashboard'))

@main.route('/prazo/toggle_status/<int:prazo_id>', methods=['POST'])
@login_required
def toggle_status_prazo(prazo_id):
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    try:
        prazo.status = not prazo.status
        if prazo.status:
            prazo.data_conclusao = datetime.utcnow().date()
            prazo.completed_by = current_user.id
            acao = "concluído"
        else:
            prazo.data_conclusao = None
            prazo.completed_by = None
            acao = "reaberto"
        db.session.commit()
        flash('Status do prazo atualizado!', 'success')
        
        # Notifica os envolvidos: usuários compartilhados e o criador
        notificados = set()
        prazo_users = prazo.shared_with.all() if hasattr(prazo.shared_with, 'all') else prazo.shared_with
        for user in prazo_users:
            notificados.add(user)
        notificados.add(prazo.user)
        notificados = [user for user in notificados if user.id != current_user.id]
        for user in notificados:
            mensagem = f"{current_user.nickname} marcou o prazo '{prazo.assunto}' como {acao}."
            link = url_for('main.prazo_info', prazo_id=prazo.id) if 'prazo_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
            criar_notificacao(user.id, "update", mensagem, link)
        
        # Registra o histórico da alteração de status
        import json
        diff = {'status': {'old': not prazo.status, 'new': prazo.status}}
        hist = PrazoHistory(
            prazo_id=prazo.id,
            change_type='status_alterado',
            changed_by=current_user.id,
            snapshot=json.dumps(diff)
        )
        db.session.add(hist)
        db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao alterar status do prazo: {str(e)}')
        flash(f'Erro ao alterar status do prazo: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))

# Rotas para compartilhar assuntos e prazos

@main.route('/assunto/share/<int:assunto_id>', methods=['GET', 'POST'])
@login_required
def share_assunto(assunto_id):
    assunto = Assunto.query.get_or_404(assunto_id)
    if assunto.user_id != current_user.id:
        flash("Não pode compartilhar assuntos de outros usuários.", "danger")
        return redirect(url_for('main.dashboard'))
    form = ShareForm(obj=assunto)
    if form.validate_on_submit():
        # Obtém os usuários com quem o assunto será compartilhado
        novos_usuarios = form.shared_with.data
        assunto.shared_with = novos_usuarios

        db.session.commit()
        flash("Assunto e todas as tarefas associadas foram compartilhados com sucesso!", "success")
        
        # Gera notificações para os usuários (exceto o usuário atual)
        for user in novos_usuarios:
            if user.id != current_user.id:
                mensagem = f"{current_user.nickname} partilhou consigo o assunto {assunto.nome_assunto}"
                # Ajuste a rota do link conforme a sua aplicação (por exemplo, para ver detalhes do assunto)
                link = url_for('main.assunto_info', assunto_id=assunto.id) if 'assunto_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                criar_notificacao(user.id, "share_invite", mensagem, link)
        
        return redirect(url_for('main.dashboard'))
    return render_template('share_assunto.html', form=form, assunto=assunto)


@main.route('/prazo/share/<int:prazo_id>', methods=['GET', 'POST'])
@login_required
def share_prazo(prazo_id):
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    if prazo.user_id != current_user.id:
        flash("Não pode compartilhar prazos de outro usuário.", "danger")
        return redirect(url_for('main.dashboard'))
    form = ShareForm(obj=prazo)
    if form.validate_on_submit():
        novos_usuarios = form.shared_with.data
        prazo.shared_with = novos_usuarios
        db.session.commit()
        flash("Prazo compartilhado com sucesso!", "success")
        
        # Gera notificações para os usuários (exceto o usuário atual)
        for user in novos_usuarios:
            if user.id != current_user.id:
                mensagem = f"{current_user.nickname} partilhou consigo o prazo '{prazo.assunto}' (Processo: {prazo.processo})."
                link = url_for('main.prazo_info', prazo_id=prazo.id) if 'prazo_info' in current_app.jinja_env.list_templates() else url_for('main.dashboard')
                criar_notificacao(user.id, "share_invite", mensagem, link)
        
        return redirect(url_for('main.dashboard'))
    return render_template('share_prazo.html', form=form, prazo=prazo)

### ROTA PARA GUARDAR REORGANIZAÇÃO DOS ASSUNTOS NO DASHBOARD

@main.route('/update_assuntos_order', methods=['POST'])
@login_required
def update_assuntos_order():
    data = request.get_json()
    if not data or 'ordem' not in data:
        return jsonify({'status': 'error', 'message': 'Dados inválidos'}), 400
    
    ordem = data['ordem']
    try:
        for item in ordem:
            assunto_id = int(item['id'])
            new_order = int(item['sort_order'])
            assunto = Assunto.query.get(assunto_id)
            # Log para depuração
            current_app.logger.info(f"Tentando atualizar assunto {assunto_id} para ordem {new_order}")
            if assunto and assunto.user_id == current_user.id:
                assunto.sort_order = new_order
                current_app.logger.info(f"Assunto {assunto_id} atualizado com nova ordem {new_order}")
            else:
                current_app.logger.warning(f"Assunto {assunto_id} não encontrado ou não pertence ao usuário {current_user.id}")
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar ordem: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

#END ROTAS ASSUNTOS, TAREFAS E PRAZOS

#BEGIN ROTAS PARA HISTÓRICO DE ASSUNTOS, TAREFAS, PRAZOS
@main.route('/history/assunto/<int:assunto_id>')
@login_required
def history_assunto(assunto_id):
    assunto = Assunto.query.get_or_404(assunto_id)
    
    assunto_history = []  # Não estamos utilizando o histórico do assunto

    # Calcula o total de horas de todas as tarefas associadas
    total_horas = sum([t.horas for t in assunto.tarefas.all()])

    # Histórico das tarefas associadas
    tasks_history = {}
    for tarefa in assunto.tarefas.all():
        tarefa_history = TarefaHistory.query.filter_by(tarefa_id=tarefa.id)\
                                            .order_by(TarefaHistory.changed_at.desc())\
                                            .all()
        tasks_history[tarefa.id] = tarefa_history

    # Comentários associados
    comments = Comment.query.filter_by(object_type='assunto', object_id=assunto_id)\
                            .order_by(Comment.created_at.desc())\
                            .all()
    # Instancia o formulário de comentário
    form = CommentForm()
    
    # Coleta os IDs dos usuários que alteraram as tarefas (para exibir os nicknames)
    user_ids = set()
    for t_hist_list in tasks_history.values():
        for hist in t_hist_list:
            user_ids.add(hist.changed_by)
    
    from app.models import User
    users = User.query.filter(User.id.in_(list(user_ids))).all()
    user_dict = {user.id: user for user in users}
    
    # Calcula o último update dentre as tarefas associadas
    last_update = None
    last_update_user_id = None
    for tarefa in assunto.tarefas.all():
        for hist in tasks_history.get(tarefa.id, []):
            if last_update is None or hist.changed_at > last_update:
                last_update = hist.changed_at
                last_update_user_id = hist.changed_by
    
    return render_template('history_assunto.html',
                           assunto=assunto,
                           history_entries=assunto_history,
                           tasks_history=tasks_history,
                           comments=comments,
                           form=form,
                           user_dict=user_dict,
                           total_horas=total_horas,
                           last_update=last_update,
                           last_update_user_id=last_update_user_id)


@main.route('/history/prazo/<int:prazo_id>')
@login_required
def history_prazo(prazo_id):
    prazo = PrazoJudicial.query.get_or_404(prazo_id)
    
    # Opcional: se houver histórico específico do prazo, pode ser carregado aqui
    # Para simplificar, vamos assumir que usaremos apenas informações registradas no próprio PrazoJudicial
    # Ou se houver PrazoHistory:
    prazo_history = PrazoHistory.query.filter_by(prazo_id=prazo.id)\
                                      .order_by(PrazoHistory.changed_at.desc())\
                                      .all()
    
    # Calcula o "total de horas" – pode ser o valor armazenado em prazo.horas
    total_horas = prazo.horas
    
    # Comentários associados ao prazo
    comments = Comment.query.filter_by(object_type='prazo', object_id=prazo.id)\
                            .order_by(Comment.created_at.desc())\
                            .all()
    form = CommentForm()
    
    # Coleta IDs dos usuários envolvidos no histórico (se houver)
    user_ids = set()
    for hist in prazo_history:
        user_ids.add(hist.changed_by)
    from app.models import User
    users = User.query.filter(User.id.in_(list(user_ids))).all()
    user_dict = { user.id: user for user in users }
    
    # Se desejar calcular o último update, de forma semelhante aos assuntos:
    last_update = None
    last_update_user_id = None
    for hist in prazo_history:
        if last_update is None or hist.changed_at > last_update:
            last_update = hist.changed_at
            last_update_user_id = hist.changed_by
    
    return render_template('history_prazo.html',
                           prazo=prazo,
                           prazo_history=prazo_history,
                           comments=comments,
                           form=form,
                           user_dict=user_dict,
                           total_horas=total_horas,
                           last_update=last_update,
                           last_update_user_id=last_update_user_id)

@main.route('/add_comment', methods=['POST'])
@login_required
def add_comment():
    object_type = request.form.get('object_type')
    object_id = request.form.get('object_id')
    comment_text = request.form.get('comment_text')
    if object_type and object_id and comment_text:
        comment = Comment(
            object_type=object_type,
            object_id=int(object_id),
            user_id=current_user.id,
            comment_text=comment_text
        )
        db.session.add(comment)
        db.session.commit()
        flash("Comentário adicionado.", "success")
        # Envia notificação para os usuários envolvidos conforme o tipo do objeto
        if object_type == 'assunto':
            # Carrega o assunto
            assunto = Assunto.query.get_or_404(object_id)

            # Identifica os usuários envolvidos: criador e os compartilhados
            compartilhados = list(assunto.shared_with)
            envolvidos = set([assunto.user])
            envolvidos.update(compartilhados)
            
            # Remove o usuário que fez o comentário
            envolvidos = [user for user in envolvidos if user.id != current_user.id]
            
            # Define a mensagem e o link (p. ex., para a página de histórico do assunto)
            mensagem = f"{current_user.nickname} adicionou um comentário no assunto '{assunto.nome_assunto}'."
            link = url_for('main.history_assunto', assunto_id=assunto.id)
            for user in envolvidos:
                criar_notificacao(user.id, "update", mensagem, link)
        
        elif object_type == 'prazo':
            # Carrega o prazo
            prazo = PrazoJudicial.query.get_or_404(object_id)

            # Identifica os usuários envolvidos: criador e os compartilhados do prazo
            compartilhados = list(prazo.shared_with)
            envolvidos = set([prazo.user])
            envolvidos.update(compartilhados)
            
            # Remove o usuário que comentou
            envolvidos = [user for user in envolvidos if user.id != current_user.id]
            
            # Define a mensagem e o link para o histórico do prazo
            mensagem = f"{current_user.nickname} adicionou um comentário no prazo '{prazo.assunto}' (Processo: {prazo.processo})."
            link = url_for('main.history_prazo', prazo_id=prazo.id)
            for user in envolvidos:
                criar_notificacao(user.id, "update", mensagem, link)
    else: 
        flash("Preencha todos os dados.", "danger")
    
    # Redireciona de volta para a página de histórico de acordo com o objeto
    if object_type == 'assunto':
        return redirect(url_for('main.history_assunto', assunto_id=object_id))
    elif object_type == 'prazo':
        return redirect(url_for('main.history_prazo', prazo_id=object_id))
    return redirect(url_for('main.dashboard'))


#END ROTAS PARA HISTÓRICO DE ASSUNTOS, TAREFAS, PRAZOS

#BEGIN ROTAS CLIENTES
### ROTAS PARA CLIENTES E HISTÓRICO ###
@main.route('/clientes')
@login_required
def clientes():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    query = Client.query.filter(
    or_(
        Client.user_id == current_user.id,
        Client.shares.any(ClientShare.user_id == current_user.id)
        )
    )
    if search:
        query = query.filter(
            or_(
                Client.name.ilike(f'%{search}%'),
                Client.number_interno.ilike(f'%{search}%')
            )
        )
    pagination = query.order_by(func.lower(Client.name)).paginate(page=page, per_page=10)
    clients = pagination.items
    return render_template('clientes.html', clients=clients, pagination=pagination, search=search)

@main.route('/client/create', methods=['GET', 'POST'])
@login_required
def create_client():
    form = ClientForm()
    if form.validate_on_submit():
        try:
            new_client = Client(
                user_id=current_user.id,
                name=form.name.data.strip(),
                number_interno=form.number_interno.data.strip() if form.number_interno.data else None,
                nif=form.nif.data.strip() if form.nif.data else None,
                address=form.address.data.strip() if form.address.data else None,
                email=form.email.data.strip() if form.email.data else None,
                telephone=form.telephone.data.strip() if form.telephone.data else None
            )
            # Se o usuário selecionar partilha, associe os usuários
            if form.shared_with.data:
                new_client.shared_with = form.shared_with.data
            db.session.add(new_client)
            db.session.commit()
            flash("Cliente criado com sucesso!", "success")
            return redirect(url_for('main.clientes'))
        except IntegrityError as e:
            db.session.rollback()
            if "UNIQUE constraint failed: clients.name" in str(e.orig):
                flash("O nome do cliente já está registrado. Por favor, escolha outro nome.", "danger")
            else:
                flash(f"Erro ao criar cliente: {str(e)}", "danger")
            current_app.logger.error(f'Erro ao criar cliente: {str(e)}')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao criar cliente: {str(e)}')
            flash(f"Erro ao criar cliente: {str(e)}", "danger")
    return render_template('create_client.html', form=form)

@main.route('/upload_client_csv', methods=['GET', 'POST'])
@login_required
def upload_client_csv():
    from app.accounting.forms import UploadCSVForm
    form = UploadCSVForm()
    if form.validate_on_submit():
        file = form.csv_file.data
        try:
            # Lê e processa o CSV
            sample = file.read(1024).decode('utf-8')
            file.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            stream = StringIO(file.read().decode('utf-8'))
            reader = csv.DictReader(stream, dialect=dialect)
            registros = []
            for row in reader:
                normalized_row = {normalize_header(k): (v.strip() if v else '') for k, v in row.items()}
                registros.append(normalized_row)
            flash(f"{len(registros)} registros foram lidos com sucesso.", "success")
            session['client_csv_registros'] = registros
            # Direciona para a pré-visualização
            return redirect(url_for('main.preview_client_csv'))
        except Exception as e:
            flash("Erro ao processar o arquivo: " + str(e), "danger")
    return render_template('upload_client_csv.html', form=form)

@main.route('/preview_client_csv', methods=['GET', 'POST'])
@login_required
def preview_client_csv():
    registros = session.get('client_csv_registros', [])
    if not registros:
        flash("Nenhum registro para pré-visualizar. Importe um arquivo primeiro.", "warning")
        return redirect(url_for('main.upload_client_csv'))
    # Neste exemplo não vamos separar conflitos – aplicamos as regras na importação.
    return render_template('preview_client_csv.html', registros=registros)

@main.route('/confirm_client_csv_import', methods=['POST'])
@login_required
def confirm_client_csv_import():
    registros = session.get('client_csv_registros', [])
    if not registros:
        flash("Não há registros para importar.", "danger")
        return redirect(url_for('main.upload_client_csv'))
    
    # Remove os registros da sessão para evitar reprocessamento
    session.pop('client_csv_registros', None)
    
    imported_count = 0
    for row in registros:
        # Extração dos campos (garanta que normalize_header está adequado)
        name = (row.get('client') or row.get('cliente') or row.get('name') or row.get('nome') or '').strip()
        if not name:
            continue
        number_interno = (row.get('number_interno') or row.get('numero_interno') or row.get('numero') or '').strip()
        nif = (row.get('nif') or '').strip()
        address = (row.get('endereço') or row.get('morada') or row.get('address') or row.get('endereco') or '').strip()
        email = (row.get('email') or '').strip()
        telephone = (row.get('telefone') or row.get('telephone') or row.get('tel') or '').strip()
        
        client = None
        # Se houver NIF, procura por cliente com esse NIF
        if nif:
            client = Client.query.filter_by(nif=nif, user_id=current_user.id).first()
        # Se não encontrou e houver número_interno, usa esse campo
        if not client and number_interno:
            client = Client.query.filter_by(number_interno=number_interno, user_id=current_user.id).first()
        
        if client:
            # Mesmo se o nome for diferente, se os identificadores forem iguais, atualiza todos os dados.
            client.name = name
            client.number_interno = number_interno or client.number_interno
            client.nif = nif or client.nif
            client.address = address or client.address
            client.email = email or client.email
            client.telephone = telephone or client.telephone
        else:
            # Caso não seja encontrado por NIF ou número_interno, tenta encontrar por nome
            existing_by_name = Client.query.filter_by(name=name, user_id=current_user.id).first()
            if existing_by_name:
                # Se já existir um cliente com o mesmo nome, mas os identificadores (NIF/numero_interno) não correspondem,
                # cria um novo cliente com o nome alterado para evitar conflitos com UNIQUE.
                new_name = "(1) " + name
            else:
                new_name = name
            client = Client(
                user_id=current_user.id,
                name=new_name,
                number_interno=number_interno,
                nif=nif,
                address=address,
                email=email,
                telephone=telephone
            )
            db.session.add(client)
        imported_count += 1

    try:
        db.session.commit()
        flash(f"{imported_count} clientes foram importados/atualizados com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao importar clientes: {e}", "danger")
    
    return redirect(url_for('main.clientes'))


@main.route('/client_info/<int:client_id>')
@login_required
def client_info(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('client_info.html', client=client)

@main.route('/client/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.name = request.form.get('name')
        client.number_interno = request.form.get('number_interno')
        client.nif = request.form.get('nif')
        client.address = request.form.get('address')
        client.email = request.form.get('email')
        client.telephone = request.form.get('telephone')
        try:
            db.session.commit()
            flash("Cliente atualizado com sucesso!", "success")
            return redirect(url_for('main.client_info', client_id=client.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao atualizar cliente: {str(e)}')
            flash(f"Erro ao atualizar cliente: {str(e)}", "danger")
            return redirect(url_for('main.edit_client', client_id=client.id))
    return render_template('edit_client.html', client=client)

#rotas para partilhar clientes

@main.route('/share_client/<int:client_id>', methods=['GET', 'POST'])
@login_required
def share_client(client_id):
    client = Client.query.get_or_404(client_id)
    form = ShareForm()  # Já existe o seu ShareForm com o campo shared_with

    # Preencha as choices do campo shared_with, se necessário:
    # form.shared_with.query = User.query.filter(...)

    if form.validate_on_submit():
        client.shared_with = form.shared_with.data
        db.session.commit()
        flash("Compartilhamento atualizado com sucesso!", "success")
        
        #partilhar clientes
        for user in form.shared_with.data:
            if user.id != current_user.id:
                mensagem = f"{current_user.nickname} partilhou consigo o cliente {client.name}"
                link = url_for('main.verificar_cliente_partilhado', cliente_id=client.id)
                criar_notificacao(
                    user.id,
                    "share_invite",
                    mensagem,
                    link,
                    extra_data={"cliente_id": int(client.id)}
                )

        return redirect(url_for('main.clientes'))

    return render_template('partilhar_cliente.html', client=client, form=form)

@main.route('/verificar_cliente_partilhado/<int:cliente_id>')
@login_required
def verificar_cliente_partilhado(cliente_id):
    cliente_partilhado = Client.query.get_or_404(cliente_id)

    # Tenta encontrar um cliente existente para o User 2
    if cliente_partilhado.number_interno:
        cliente_existente = Client.query.filter_by(
            user_id=current_user.id,
            number_interno=cliente_partilhado.number_interno
        ).first()
    else:
        cliente_existente = Client.query.filter(
            Client.user_id == current_user.id,
            func.lower(Client.name) == cliente_partilhado.name.lower()
        ).first()

    # Marcar todas as notificações do tipo 'share_invite' relacionadas a este cliente como lidas
    notifs = Notification.query.filter_by(
        user_id=current_user.id,
        type="share_invite",
        is_read=False
    ).all()
    for notif in notifs:
        # Se a notificação extra_data contiver o cliente_id igual ao que estamos verificando
        if notif.extra.get('cliente_id') == cliente_partilhado.id:
            notif.is_read = True
    db.session.commit()

    return render_template('verificar_cliente.html',
                           cliente_partilhado=cliente_partilhado,
                           cliente_existente=cliente_existente)


@main.route('/resolver_conflitos_cliente/<int:cliente_existente_id>', methods=['POST'])
@login_required
def resolver_conflitos_cliente(cliente_existente_id):
    cliente_existente = Client.query.filter_by(id=cliente_existente_id, user_id=current_user.id).first_or_404()
    cliente_partilhado_id = request.form.get('cliente_partilhado_id')
    cliente_partilhado = Client.query.get(cliente_partilhado_id)

    # Lista de campos a resolver
    campos = ['name', 'number_interno', 'nif', 'address', 'email', 'telephone']
    for campo in campos:
        choice = request.form.get(f"{campo}_choice")
        if choice == 'user1':
            setattr(cliente_existente, campo, getattr(cliente_partilhado, campo))
        # Se a escolha for 'user2', mantemos o valor atual; se desejar concatenar ou outro tratamento, ajuste aqui.

    db.session.commit()
    flash("Informações do cliente atualizadas com sucesso!", "success")
    return redirect(url_for('main.client_info', client_id=cliente_existente.id))

@main.route('/criar_cliente_partilhado/<int:cliente_partilhado_id>')
@login_required
def criar_cliente_partilhado(cliente_partilhado_id):
    cliente_partilhado = Client.query.get_or_404(cliente_partilhado_id)
    # Verifica se já existe um cliente com o mesmo nome para o usuário atual
    existente = Client.query.filter_by(user_id=current_user.id, name=cliente_partilhado.name).first()
    if existente:
        flash("Você já possui um cliente com esse nome. Por favor, verifique.", "warning")
        return redirect(url_for('main.client_info', client_id=existente.id))
    
    # Caso contrário, cria a cópia
    novo_cliente = Client(
        user_id=current_user.id,
        name=cliente_partilhado.name,
        number_interno=cliente_partilhado.number_interno,
        nif=cliente_partilhado.nif,
        address=cliente_partilhado.address,
        email=cliente_partilhado.email,
        telephone=cliente_partilhado.telephone
    )
    db.session.add(novo_cliente)
    db.session.commit()
    flash("Novo cliente criado com os dados partilhados!", "success")
    return redirect(url_for('main.client_info', client_id=novo_cliente.id))

from sqlalchemy import or_
from app.models import Assunto, PrazoJudicial, Comment, TarefaHistory, PrazoHistory, User
from app.forms import CommentForm

@main.route('/historico/<int:client_id>')
@login_required
def historico_cliente(client_id):
    client = Client.query.get_or_404(client_id)
    
    # Filtra os assuntos usando uma query para incluir os compartilhados
    assuntos_filtrados = Assunto.query.filter(
        Assunto.client.has(Client.number_interno == client.number_interno),
        or_(
            Assunto.user_id == current_user.id,
            Assunto.shared_with.any(User.id == current_user.id)
        )
    ).all()

    assuntos_concluidos = [a for a in assuntos_filtrados if a.is_completed]
    assuntos_pendentes = [a for a in assuntos_filtrados if not a.is_completed]
    
    # Filtra os prazos de forma semelhante
    prazos_filtrados = PrazoJudicial.query.filter(
        PrazoJudicial.client.has(Client.number_interno == client.number_interno),
        or_(
            PrazoJudicial.user_id == current_user.id,
            PrazoJudicial.shared_with.any(User.id == current_user.id)
        )
    ).all()

    prazos_concluidos = [p for p in prazos_filtrados if p.status]
    prazos_pendentes = [p for p in prazos_filtrados if not p.status]
    
    # (Opcional) Reúne tarefas para possível uso
    tarefas_concluidas = []
    tarefas_pendentes = []
    for assunto in assuntos_filtrados:
        for tarefa in assunto.tarefas:
            if tarefa.is_completed:
                tarefas_concluidas.append(tarefa)
            else:
                tarefas_pendentes.append(tarefa)
    
    # Comentários dos assuntos
    comment_assunto = {}
    for assunto in assuntos_filtrados:
        comment_assunto[assunto.id] = Comment.query.filter_by(
            object_type='assunto', object_id=assunto.id
        ).order_by(Comment.created_at.desc()).all()
    
    # Comentários dos prazos
    comment_prazo = {}
    for prazo in prazos_filtrados:
        comment_prazo[prazo.id] = Comment.query.filter_by(
            object_type='prazo', object_id=prazo.id
        ).order_by(Comment.created_at.desc()).all()
    
    # Histórico de tarefas
    tasks_history = {}
    for assunto in assuntos_filtrados:
        for tarefa in assunto.tarefas:
            tasks_history[tarefa.id] = TarefaHistory.query.filter_by(
                tarefa_id=tarefa.id
            ).order_by(TarefaHistory.changed_at.desc()).all()
    
    # Histórico de prazos
    prazo_history = {}
    for prazo in prazos_filtrados:
        prazo_history[prazo.id] = PrazoHistory.query.filter_by(
            prazo_id=prazo.id
        ).order_by(PrazoHistory.changed_at.desc()).all()
    
    # Constrói um dicionário de usuários envolvidos nos históricos e comentários
    user_ids = set()
    for tarefa_hist in tasks_history.values():
        for hist in tarefa_hist:
            user_ids.add(hist.changed_by)
    for prazo_hist in prazo_history.values():
        for hist in prazo_hist:
            user_ids.add(hist.changed_by)
    for comments in comment_assunto.values():
        for comment in comments:
            user_ids.add(comment.user_id)
    for comments in comment_prazo.values():
        for comment in comments:
            user_ids.add(comment.user_id)
    user_dict = {u.id: u for u in User.query.filter(User.id.in_(list(user_ids))).all()}
    
    # Instancia os formulários para comentários
    form = CommentForm()
    prazo_form = CommentForm()
    
    return render_template(
        'historico.html',
        client=client,
        assuntos_concluidos=assuntos_concluidos,
        assuntos_pendentes=assuntos_pendentes,
        prazos_concluidos=prazos_concluidos,
        prazos_pendentes=prazos_pendentes,
        prazos=prazos_filtrados,
        tarefas_concluidas=tarefas_concluidas,
        tarefas_pendentes=tarefas_pendentes,
        comment_assunto=comment_assunto,
        comment_prazo=comment_prazo,
        tasks_history=tasks_history,
        prazo_history=prazo_history,
        user_dict=user_dict,
        form=form,
        prazo_form=prazo_form
    )


#END ROTAS CLIENTES


#BEGIN ROTAS BILLING
#Rotas para Billing

@main.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    if request.method == "POST":
        selected_items = request.form.getlist('items')
        if not selected_items:
            flash("Nenhum item selecionado.", "warning")
            return redirect(url_for('main.billing'))
        
        # Agrupar os itens selecionados por cliente
        client_groups = {}
        for sel in selected_items:
            t, id_str = sel.split('-')
            item_id = int(id_str)
            if t == 'assunto':
                item = Assunto.query.get(item_id)
                client_id = item.client_id
                group = client_groups.setdefault(client_id, {"subjects": set(), "tasks": set(), "prazos": set()})
                group["subjects"].add(item_id)
            elif t == 'tarefa':
                item = Tarefa.query.get(item_id)
                client_id = item.assunto.client_id
                group = client_groups.setdefault(client_id, {"subjects": set(), "tasks": set(), "prazos": set()})
                group["tasks"].add(item_id)
            elif t == 'prazo':
                item = PrazoJudicial.query.get(item_id)
                client_id = item.client_id
                group = client_groups.setdefault(client_id, {"subjects": set(), "tasks": set(), "prazos": set()})
                group["prazos"].add(item_id)
            else:
                flash("Tipo de item inválido.", "danger")
                return redirect(url_for('main.billing'))
        #Processar cada grupo
        for client_id, items in client_groups.items():
            total_hours = 0
            details_lines = []
            # Processar Assuntos selecionados – incluir todas as tarefas deste assunto
            for subj_id in items["subjects"]:
                subj = Assunto.query.get(subj_id)
                subj.is_billed = True
                details_lines.append(f"Assunto: {subj.nome_assunto}")
                registros_assunto = HoraAdicao.query.filter_by(item_type='assunto', item_id=subj.id).all()
                for reg in registros_assunto:
                    usuario = User.query.get(reg.user_id)
                    details_lines.append(
                        f"  [Assunto] Horas adicionadas: {reg.horas_adicionadas}h por usuário {usuario.username} em {reg.timestamp.strftime('%d/%m/%Y %H:%M')}"
                    )
                for task in subj.tarefas:
                    if task.is_completed and not task.is_billed:
                        task.is_billed = True
                        total_hours += task.horas
                        completion_date = task.data_conclusao.strftime('%d/%m/%Y') if task.data_conclusao else "N/A"
                        registros_tarefa = HoraAdicao.query.filter_by(item_type='tarefa', item_id=task.id).all()
                        detalhe_tarefa = f"  Tarefa: {task.nome_tarefa}, Horas: {task.horas}h, Concluída em: {completion_date}"
                        for reg in registros_tarefa:
                            usuario = User.query.get(reg.user_id)
                            detalhe_tarefa += f"\n     [Tarefa] Horas adicionadas: {reg.horas_adicionadas}h por usuário {usuario.username} em {reg.timestamp.strftime('%d/%m/%Y %H:%M')}"
                        details_lines.append(detalhe_tarefa)
            
            # Processar Tarefas selecionadas individualmente (evitando duplicidade)
            for task_id in items["tasks"]:
                task = Tarefa.query.get(task_id)
                if task.assunto.id in items["subjects"]:
                    continue
                if task.is_completed and not task.is_billed:
                    task.is_billed = True
                    total_hours += task.horas
                    completion_date = task.data_conclusao.strftime('%d/%m/%Y') if task.data_conclusao else "N/A"
                    registros_tarefa = HoraAdicao.query.filter_by(item_type='tarefa', item_id=task.id).all()
                    detalhe_tarefa = f"Tarefa: {task.nome_tarefa}, Horas: {task.horas}h, Concluída em: {completion_date}"
                    for reg in registros_tarefa:
                        usuario = User.query.get(reg.user_id)
                        detalhe_tarefa += f"\n     [Tarefa] Horas adicionadas: {reg.horas_adicionadas}h por usuário {usuario.username} em {reg.timestamp.strftime('%d/%m/%Y %H:%M')}"
                    details_lines.append(detalhe_tarefa)
            
            # Processar Prazos selecionados
            for prazo_id in items["prazos"]:
                prazo = PrazoJudicial.query.get(prazo_id)
                prazo.is_billed = True
                total_hours += prazo.horas
                data_conclusao = prazo.data_conclusao.strftime('%d/%m/%Y') if prazo.data_conclusao else "N/A"
                detalhe_prazo = f"Prazo: {prazo.assunto} (Processo: {prazo.processo}), Horas: {prazo.horas}h, Concluído em: {data_conclusao}"
                registros_prazo = HoraAdicao.query.filter_by(item_type='prazo', item_id=prazo.id).all()
                for reg in registros_prazo:
                    usuario = User.query.get(reg.user_id)
                    detalhe_prazo += f"\n     [Prazo] Horas adicionadas: {reg.horas_adicionadas}h por usuário {usuario.username} em {reg.timestamp.strftime('%d/%m/%Y %H:%M')}"
                details_lines.append(detalhe_prazo)
            
            #Criar nota de honorários para o current user
            nota = NotaHonorarios(
                user_id=current_user.id,
                client_id=client_id,
                total_hours=total_hours,
                details="\n".join(details_lines),
                is_confirmed=True
            )
            db.session.add(nota)

            # NOTIFICAÇÃO: inicie o loop de notificação para este grupo (cliente)
            shared_client = Client.query.get(client_id)
            # Garanta que o relacionamento 'shares' retorne todos os registros (usando .all())
            shared_users = [share.user for share in shared_client.shares.all()]
            # Recupere o dono do cliente a partir do user_id
            client_owner = User.query.get(shared_client.user_id)
            # Construa o conjunto de envolvidos (incluindo o dono e os compartilhados)
            envolvidos = set(shared_users + [client_owner])
            
            # Para cada usuário diferente do current_user, cria uma cópia da nota e envia notificação
            for u in envolvidos:
                if u.id != current_user.id:
                    nota_copia = NotaHonorarios(
                        user_id=u.id,
                        client_id=client_id,
                        total_hours=total_hours,
                        details="\n".join(details_lines),
                        is_confirmed=True
                    )
                    db.session.add(nota_copia)
                    mensagem = f"{current_user.nickname} gerou nota de honorários para o cliente {shared_client.name}."
                    link = url_for('main.client_info', client_id=shared_client.id)
                    criar_notificacao(u.id, "billing", mensagem, link)
            
        db.session.commit()
        flash("Notas de honorários geradas com sucesso!", "success")
        return redirect(url_for('main.billing'))
    else:
        # GET: incluir todos os itens (próximos de faturamento), sejam do usuário ou compartilhados
        billable_assuntos = Assunto.query.filter(
            Assunto.is_completed == True,
            Assunto.is_billed == False,
            or_(
                Assunto.user_id == current_user.id,
                Assunto.shared_with.any(id=current_user.id),
                Assunto.completed_by == current_user.id
            )
        ).all()
        grouped_data = {}
        for a in billable_assuntos:
            c_id = a.client_id
            if c_id not in grouped_data:
                grouped_data[c_id] = {"client": a.client, "assuntos": {}, "prazos": []}
            # Inclua todas as tarefas concluídas do assunto
            tasks = Tarefa.query.filter(
                Tarefa.assunto_id == a.id,
                Tarefa.is_completed == True,
                Tarefa.is_billed == False
            ).all()
            grouped_data[c_id]["assuntos"][a.id] = {"assunto": a, "tarefas": tasks}
        
         # Adicionar tarefas concluídas que não foram incluídas no agrupamento por assunto       
        billable_tarefas = Tarefa.query.filter(
            Tarefa.is_completed == True,
            Tarefa.is_billed == False,
        ).all()
        for t in billable_tarefas:
            subj_id = t.assunto.id
            c_id = t.assunto.client_id
            # Se o assunto não estiver no agrupamento ou se a tarefa não estiver listada, adicione-a
            if c_id not in grouped_data:
                grouped_data[c_id] = {"client": t.assunto.client, "assuntos": {}, "prazos": []}
            if subj_id not in grouped_data[c_id]["assuntos"]:
                grouped_data[c_id]["assuntos"][subj_id] = {"assunto": t.assunto, "tarefas": []}
            # Verifique se a tarefa já não está listada (evita duplicidade)
            if t not in grouped_data[c_id]["assuntos"][subj_id]["tarefas"]:
                grouped_data[c_id]["assuntos"][subj_id]["tarefas"].append(t)


        billable_prazos = PrazoJudicial.query.filter(
            PrazoJudicial.status == True,
            PrazoJudicial.is_billed == False,
            or_(
                PrazoJudicial.user_id == current_user.id,
                PrazoJudicial.shared_with.any(id=current_user.id),
                PrazoJudicial.completed_by == current_user.id
            )
        ).all()
        for p in billable_prazos:
            c_id = p.client_id
            if c_id not in grouped_data:
                grouped_data[c_id] = {"client": p.client, "assuntos": {}, "prazos": []}
            grouped_data[c_id]["prazos"].append(p)
        
        # Mostrar apenas as notas emitidas pelo usuário atual
        nota_honorarios = NotaHonorarios.query.filter_by(user_id=current_user.id).order_by(NotaHonorarios.created_at.desc()).all()
        return render_template('billing_grouped.html', grouped_data=grouped_data, nota_honorarios=nota_honorarios)


@main.route('/billing/historico')
@login_required
def billing_historico():
    page = request.args.get('page', 1, type=int)
    
    from sqlalchemy.orm import aliased

    ClientAlias = aliased(Client)

    # Subquery para os números internos dos clientes pertencentes ao current_user
    subq = db.session.query(Client.number_interno).filter(Client.user_id == current_user.id).subquery()
    subq_select = select(subq)

    query = (
        NotaHonorarios.query
        .join(ClientAlias, NotaHonorarios.client_id == ClientAlias.id)
        .filter(
            or_(
                ClientAlias.user_id == current_user.id,
                ClientAlias.number_interno.in_(subq_select)
            )
        )
    )
    # Filtros adicionais
    cliente = request.args.get('cliente', '').strip()
    if cliente:
        query = query.filter(func.lower(ClientAlias.name).ilike(func.lower(f"%{cliente}%")))

    data_emissao = request.args.get('data_emissao', '').strip()
    if data_emissao:
        try:
            from datetime import datetime
            dt = datetime.strptime(data_emissao, '%Y-%m-%d')
            query = query.filter(NotaHonorarios.created_at >= dt)
        except ValueError:
            pass

    min_horas = request.args.get('min_horas', '').strip()
    if min_horas:
        try:
            min_horas = float(min_horas)
            query = query.filter(NotaHonorarios.total_hours >= min_horas)
        except ValueError:
            pass

    # Filtro pelo título (assunto/prazo) - se necessário:
    titulo = request.args.get('titulo', '').strip()
    if titulo:
        query = query.filter(NotaHonorarios.details.ilike(f"%{titulo}%"))

    query = query.order_by(NotaHonorarios.created_at.desc())
    pagination = query.paginate(page=page, per_page=5)
    return render_template('billing_historico.html', nota_honorarios=pagination.items, pagination=pagination)


@main.route('/billing_cliente/<int:client_id>')
@login_required
def billing_cliente(client_id):
    client = Client.query.get_or_404(client_id)
    billing_notes = NotaHonorarios.query.filter(
        NotaHonorarios.client_id == client_id,
        or_(
            NotaHonorarios.user_id == current_user.id,
            NotaHonorarios.client.has(Client.shares.any(ClientShare.user_id == current_user.id))
        )
    ).order_by(NotaHonorarios.created_at.desc()).all()
    return render_template('billing_cliente.html', client=client, billing_notes=billing_notes)

@main.route('/billing/revert/<string:item_type>/<int:item_id>', methods=['POST'])
@login_required
def revert_billing(item_type, item_id):
    # Determinar o item e as permissões (ampliando para usuários em partilha)
    if item_type == 'assunto':
        item = Assunto.query.get_or_404(item_id)
        can_revert = (
            item.user_id == current_user.id or
            (item.completed_by and item.completed_by == current_user.id) or
            (current_user in item.shared_with)
        )
    elif item_type == 'tarefa':
        item = Tarefa.query.get_or_404(item_id)
        can_revert = (
            item.user_id == current_user.id or
            (item.completed_by and item.completed_by == current_user.id) or
            (current_user in item.assunto.shared_with)
        )
    elif item_type == 'prazo':
        item = PrazoJudicial.query.get_or_404(item_id)
        can_revert = (
            item.user_id == current_user.id or
            (item.completed_by and item.completed_by == current_user.id) or
            (current_user in item.shared_with)
        )
    else:
        flash("Tipo de item inválido.", "danger")
        return redirect(url_for('main.billing'))
    
    if not can_revert:
        flash("Você não tem permissão para reverter o faturamento deste item.", "danger")
        return redirect(url_for('main.billing'))
    
    # Processa a reversão conforme o tipo:
    if item_type == 'prazo':
        # Para prazos, reverte faturamento e status
        item.is_billed = False
        item.status = False
        item.data_conclusao = None
        item.completed_by = None
    elif item_type == 'assunto':
        # Reverter o assunto – altera os indicadores do assunto...
        item.is_billed = False
        item.is_completed = False
        item.data_conclusao = None
        item.completed_by = None
        # ...e também reverter todas as tarefas do assunto
        for tarefa in item.tarefas:
            if tarefa.is_completed:
                tarefa.is_billed = False
                tarefa.is_completed = False
                tarefa.data_conclusao = None
                tarefa.completed_by = None
    elif item_type == 'tarefa':
        # Reverter a tarefa individual
        item.is_billed = False
        item.is_completed = False
        item.data_conclusao = None
        item.completed_by = None
        db.session.commit()
        # Se essa foi a última tarefa concluída do assunto, reverte também o assunto
        subject = item.assunto
        remaining = Tarefa.query.filter_by(assunto_id=subject.id, is_completed=True).count()
        if remaining == 0:
            subject.is_completed = False
            subject.data_conclusao = None
            subject.completed_by = None

    # Prepara os usuários a serem notificados
    notified_users = set()
    if item_type == 'assunto':
        # Notifica todos os usuários compartilhados e o criador do assunto
        notified_users.update(item.shared_with)
        notified_users.add(item.user)
    elif item_type == 'tarefa':
        # Notifica os compartilhados do assunto e o criador do assunto
        notified_users.update(item.assunto.shared_with)
        notified_users.add(item.assunto.user)
    elif item_type == 'prazo':
        notified_users.update(item.shared_with)
        notified_users.add(item.user)
    
    # Remove o usuário que está efetuando a reversão da lista
    notified_users = {u for u in notified_users if u.id != current_user.id}

    # Define a mensagem e link da notificação conforme o tipo
    if item_type == 'assunto':
        mensagem = f"{current_user.nickname} reverteu o faturamento do assunto '{item.nome_assunto}'."
    elif item_type == 'tarefa':
        mensagem = f"{current_user.nickname} reverteu o faturamento da tarefa '{item.nome_tarefa}' do assunto '{item.assunto.nome_assunto}'."
    elif item_type == 'prazo':
        mensagem = f"{current_user.nickname} reverteu o faturamento do prazo '{item.assunto}' (Processo: {item.processo})."
    link = url_for('main.billing')

    # Gera a notificação para cada usuário envolvido
    for user in notified_users:
        criar_notificacao(user.id, "revert", mensagem, link)

    db.session.commit()
    flash("Item revertido para 'não concluído' e enviado para o billing.", "success")
    return redirect(url_for('main.billing'))


#END ROTAS BILLING


#BEGIN ROTAS NOTIFICAÇÕES
#Rotas para notificações

@main.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False)\
                               .order_by(Notification.timestamp.desc()).all()
    for n in notifs:
        current_app.logger.info(f"Notificação {n.id}: type={n.type}, extra={n.extra}")
    return render_template('notifications.html', notifications=notifs)


@main.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Sem permissão'}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({'status': 'ok'})

@main.route('/notification/view/<int:notif_id>')
@login_required
def notification_view(notif_id):
    """Marca a notificação como lida e redireciona para a página de verificação ou link associado."""
    notif = Notification.query.get_or_404(notif_id)

    # Verifica se a notificação pertence ao usuário atual
    if notif.user_id != current_user.id:
        flash("Você não tem permissão para ver essa notificação.", "danger")
        return redirect(url_for('main.notifications'))

    # Marca a notificação como lida
    notif.is_read = True
    db.session.commit()

    # Se for do tipo share_invite e tiver extra_data com cliente_id, redireciona para a verificação
    if notif.type == 'share_invite' and notif.extra.get('cliente_id'):
        return redirect(url_for('main.verificar_cliente_partilhado', cliente_id=notif.extra.get('cliente_id')))

    # Caso contrário, redireciona para o link ou para o dashboard
    if notif.link:
        return redirect(notif.link)
    else:
        return redirect(url_for('main.dashboard'))


@main.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        notifs_nao_lidas = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).order_by(Notification.timestamp.desc()).all()
        unread = len(notifs_nao_lidas)
        return dict(notifications=notifs_nao_lidas, unread_count=unread)
    return dict(notifications=[], unread_count=0)

@main.route('/notifications/historico')
@login_required
def notifications_historico():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Defina quantas notificações serão exibidas por página
    pagination = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=True
    ).order_by(Notification.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)

    notifications = pagination.items

    # Verifica se a requisição é via AJAX (usando o cabeçalho)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        notif_list = []
        for notif in notifications:
            notif_list.append({
                'message': notif.message,
                'timestamp': notif.timestamp.strftime('%d/%m/%Y %H:%M')
            })
        return jsonify(notifications=notif_list, has_next=pagination.has_next)

    return render_template('notifications_historico.html', notifications=notifications)


def criar_notificacao(user_id, tipo, mensagem, link=None, extra_data=None):
    if extra_data is None:
        extra_data = {}
    # Converte o dicionário extra_data para uma string JSON
    extra_data_json = json.dumps(extra_data)
    notif = Notification(
        user_id=user_id,
        type=tipo,
        message=mensagem,
        link=link,
        extra_data=extra_data_json
    )
    db.session.add(notif)
    db.session.commit()


@main.route('/notifications/respond_share/<int:notif_id>/<string:acao>', methods=['POST'])
@login_required
def respond_share(notif_id, acao):
    # acao pode ser 'accept' ou 'decline'
    notif = Notification.query.get_or_404(notif_id)
    # Verifique se o usuário tem permissão
    if notif.user_id != current_user.id:
        flash("Você não tem permissão para responder essa notificação.", "danger")
        return redirect(url_for('main.notifications'))
    # Processa a ação, por exemplo, atualize a partilha do item com base em notif.extra_data
    # (Aqui você precisa implementar a lógica específica: atualizar o status da partilha no item)
    if acao == 'accept':
        # Exemplo: marcar a partilha como aceita no item compartilhado
        flash("Partilha aceita!", "success")
    else:
        flash("Partilha recusada.", "warning")
    # Marque a notificação como lida (ou remova-a)
    notif.is_read = True
    db.session.commit()
    return redirect(url_for('main.notifications'))
#END ROTAS NOTIFICAÇÕES

#BEGIN ROTA PRINCIPAL PARA CONTABILIDADE
#ROTA PRINCIPAL PARA CONTABILIDADE
@main.route('/contabilidade_cliente/<int:client_id>')
@login_required
def contabilidade_cliente(client_id):
    client = Client.query.get_or_404(client_id)
    contabil_docs = DocumentoContabilistico.query.filter(
        DocumentoContabilistico.client_id == client_id,
        DocumentoContabilistico.user_id == current_user.id
    ).order_by(DocumentoContabilistico.created_at.desc()).all()
    paid_docs = [doc for doc in contabil_docs if doc.is_confirmed]
    pending_docs = [doc for doc in contabil_docs if not doc.is_confirmed]
    return render_template('accounting/contabilidade_cliente.html', client=client, paid_docs=paid_docs, pending_docs=pending_docs)
#END ROTA PRINCIPAL PARA CONTABILIDADE

