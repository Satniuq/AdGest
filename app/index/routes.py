# app/index/routes.py

from flask import render_template, Blueprint, jsonify, url_for
from flask_login import login_required, current_user
from datetime import date
from app.index import index_bp
from app.dashboard.services import get_overview_data

# importa a tua classe de form de prazos
from app.prazos.forms import AddPrazoHoursForm  
# e, se o teu template usa csrf_form.csrf_token:
from flask_wtf import FlaskForm  
class CSRFForm(FlaskForm): pass

@index_bp.route('/', methods=['GET'])
@login_required
def index():
    data = get_overview_data(current_user)
    # instância do form para cada modal de “add hours”
    data['add_hours_form'] = AddPrazoHoursForm()
    # instância genérica só para o csrf_token de qualquer form inline
    data['csrf_form']      = CSRFForm()
    return render_template('index/index.html', **data)

@index_bp.route('/events')
@login_required
def calendar_events():
    data = get_overview_data(current_user)
    hoje = date.today()
    events = []

    # Tarefas
    for t in data['tasks_overdue'] + data['tasks_today'] + data['tasks_tomorrow']:
        due = t.due_date.date()
        if due < hoje:
            color = '#dc3545'
        elif due == hoje:
            color = '#0dcaf0'
        else:
            color = '#ffc107'

        events.append({
            'id':          f"task-{t.id}",
            'title':       f"{t.assunto.title} – {t.title}",
            'start':       t.due_date.isoformat(),
            'color':       color,
            # **props personalizadas no nível raiz**
            'type':        'task',
            'url_history': url_for('tarefas.history', id=t.id)
        })

    # Prazos
    for p in data['deadlines_overdue'] + data['deadlines_today'] + data['deadlines_tomorrow']:
        d = p.date
        if d < hoje:
            color = '#dc3545'
        elif d == hoje:
            color = '#0dcaf0'
        else:
            color = '#ffc107'

        events.append({
            'id':         f"prazo-{p.id}",
            'title':      f"{p.processo.external_id or p.processo.id} – {p.description}",
            'start':      d.isoformat(),
            'color':      color,
            # **props personalizadas no nível raiz**
            'type':       'deadline',
            'url_detail': url_for('prazos.detail_prazo', prazo_id=p.id)
        })

    return jsonify(events)

