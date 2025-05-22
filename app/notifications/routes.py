# app/notifications/routes.py

from app.extensions import csrf
import json
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    jsonify, request, current_app
)
from flask_login import login_required, current_user
from app.notifications.models import Notification
from app.notifications.forms import MarkReadForm
from app import db


from app.notifications import notifications_bp


@notifications_bp.route('/', methods=['GET'])
@login_required
def list_notifications():
    form = MarkReadForm()
    notifications = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).all()
    return render_template(
        'notifications.html',
        notifications=notifications,
        mark_read_form=form
    )


@csrf.exempt
@notifications_bp.route('/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    # mesmo corpo da sua função, mas sem validação CSRF
    form = MarkReadForm()
    # você pode até pular o form.validate_on_submit() se quiser testar
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify(error="Permissão negada"), 403

    try:
        notif.is_read = True
        db.session.commit()
        return '', 204
    except:
        db.session.rollback()
        return jsonify(error="Erro interno"), 500



@notifications_bp.route('/view/<int:notif_id>', methods=['GET'])
@login_required
def view_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        flash("Você não tem permissão para ver essa notificação.", "danger")
        return redirect(url_for('notifications.list_notifications'))

    # Marca como lida
    notif.is_read = True
    db.session.commit()

    # Se for convite de partilha de cliente, redireciona para a verificação
    if notif.type == 'share_invite' and notif.extra.get('cliente_id'):
        return redirect(url_for('client.verificar_cliente_partilhado', cliente_id=notif.extra['cliente_id']))

    # Caso contrário, abre o link ou o dashboard
    return redirect(notif.link or url_for('dashboard.dashboard'))


@notifications_bp.route('/historico', methods=['GET'])
@login_required
def historico_notifications():
    page = request.args.get('page', 1, type=int)
    pagination = Notification.query.filter_by(
        user_id=current_user.id, is_read=True
    ).order_by(Notification.timestamp.desc()).paginate(page=page, per_page=10, error_out=False)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # AJAX load mais
        return jsonify(
            notifications=[{
                'message': n.message,
                'timestamp': n.timestamp.strftime('%d/%m/%Y %H:%M')
            } for n in pagination.items],
            has_next=pagination.has_next
        )

    return render_template('notifications/notifications_historico.html', notifications=pagination.items, pagination=pagination)


def criar_notificacao(user_id, tipo, mensagem, link=None, extra_data=None):
    if extra_data is None:
        extra_data = {}
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


@notifications_bp.route('/respond_share/<int:notif_id>/<string:acao>', methods=['POST'])
@login_required
def respond_share(notif_id, acao):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        flash("Você não tem permissão para responder essa notificação.", "danger")
        return redirect(url_for('notifications.list_notifications'))

    # Lógica de aceitar/recusar (implemente conforme precisar)
    if acao == 'accept':
        flash("Partilha aceita!", "success")
    else:
        flash("Partilha recusada.", "warning")

    notif.is_read = True
    db.session.commit()
    return redirect(url_for('notifications.list_notifications'))
