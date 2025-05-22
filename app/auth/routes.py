# app/auth/routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Message
from app import db
from app.extensions import mail
from app.auth.forms import (
    RegistrationForm, LoginForm,
    RequestResetForm, ResetPasswordForm,
    EditProfileForm
)
from app.auth.models import User, AuditLog
from app.decorators import admin_required
from app.gcs_helpers import upload_to_gcs

from app.auth import auth_bp

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/edit_profile', methods=['GET', 'POST'])
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
                    public_url = upload_to_gcs(
                        file_obj=file_data,
                        filename=filename,
                        content_type=file_data.content_type
                    )
                    current_user.profile_image = public_url
                except Exception as e:
                    current_app.logger.error(f"Erro ao fazer upload para o GCS: {e}")
                    flash("Erro ao fazer upload da imagem. Tente novamente.", "danger")
                    return redirect(url_for("auth.edit_profile"))
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

        return redirect(url_for('auth.profile'))

    return render_template('auth/edit_profile.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
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
            role=form.role.data
        )
        db.session.add(user)
        try:
            db.session.commit()
            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('index.index'))
        except Exception:
            db.session.rollback()
            flash('O nome de usuário já está em uso. Por favor, escolha outro.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo {field}: {error}", 'danger')
    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=False)
            return redirect(url_for('index.index'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')
    return render_template('auth/login.html', form=form)


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
        flash('Se um usuário com esse e-mail existir, as instruções foram enviadas.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_request.html', form=form)


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('O token é inválido ou expirou.', 'warning')
        return redirect(url_for('auth.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.password.data)
        db.session.commit()
        flash('Senha atualizada! Faça login com a nova senha.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_token.html', form=form)


def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for('auth.reset_token', token=token, _external=True)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@seusite.com')
    msg = Message(
        'Redefinir senha - AdGest',
        sender=sender,
        recipients=[user.email]
    )
    msg.body = (
        f"Para redefinir sua senha, visite o link abaixo:\n\n"
        f"{reset_url}\n\n"
        "Se você não solicitou essa alteração, ignore este e-mail."
    )
    mail.send(msg)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
