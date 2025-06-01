# app/index/routes.py

from flask import render_template, Blueprint, jsonify, url_for
from flask_login import login_required, current_user
from datetime import date, timedelta
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
    # Pega todo o contexto que você já gera em get_overview_data()
    data = get_overview_data(current_user)

    # === Cálculo das datas e dias da semana em Português ===
    hoje = date.today()
    amanha = hoje + timedelta(days=1)
    depois = hoje + timedelta(days=2)

    # Mapeamento de weekday() para nomes em Português
    dias_semana = {
        0: "Segunda-Feira",
        1: "Terça-Feira",
        2: "Quarta-Feira",
        3: "Quinta-Feira",
        4: "Sexta-Feira",
        5: "Sábado",
        6: "Domingo"
    }
    # Formatações
    data['date_today']      = hoje.strftime('%d/%m/%Y')
    data['weekday_today']   = dias_semana[hoje.weekday()]

    data['date_tomorrow']   = amanha.strftime('%d/%m/%Y')
    data['weekday_tomorrow']= dias_semana[amanha.weekday()]

    data['date_day_after']  = depois.strftime('%d/%m/%Y')
    data['weekday_day_after']= dias_semana[depois.weekday()]
    # ==========================================================

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

