# app/dashboard/services.py

from datetime import date, timedelta
from typing import Dict, Any, List

from app.assuntos.services import AssuntoService
from app.prazos.services import PrazoService
from app.tarefas.services import TarefaService

def fetch_dashboard_data(user) -> Dict[str, Any]:
    """
    Retorna um dict com:
      - assuntos: lista de Assunto (abertos, próprios ou compartilhados)
      - prazos:   lista de PrazoJudicial (status 'open')
      - tasks_map:     { assunto_id: [Tarefa, ...] }
      - task_hours:    { tarefa_id: total_horas }
      - prazo_hours:   { prazo_id: total_horas }
      - assunto_hours: { assunto_id: total_horas_de_todas_as_tarefas }
    """
    # 1) Assuntos relevantes
    assuntos = AssuntoService.list_for_user(user.id)

    # 2) Prazos relevantes
    prazos = PrazoService.list_for_user(user.id)

    # 3) Tarefas por Assunto
    tasks_map = {
        a.id: TarefaService.list_for_assunto(a)
        for a in assuntos
    }

    # 4) Total de horas por tarefa e por prazo
    task_hours  = {
        t.id: TarefaService.task_total_hours(t)
        for ts in tasks_map.values() for t in ts
    }
    prazo_hours = {
        p.id: (p.hours_spent or 0.0)
        for p in prazos
    }

    # 5) Soma total de horas por Assunto (todas as suas tarefas)
    assunto_hours = {
        a.id: TarefaService.total_hours_for_assunto(a)
        for a in assuntos
    }

    return {
        'assuntos':      assuntos,
        'prazos':        prazos,
        'tasks_map':     tasks_map,
        'task_hours':    task_hours,
        'prazo_hours':   prazo_hours,
        'assunto_hours': assunto_hours
    }


def get_overview_data(user) -> Dict[str, Any]:
    """
    Agrega tudo para o dashboard ‘overview’:
      - hoje & amanhã
      - listas de tarefas (overdue, today, tomorrow, day_after_tomorrow)
      - listas de prazos (overdue, today, tomorrow, day_after_tomorrow)
      - contagens para KPI cards
      - rótulos de dia (day_labels) para mostrar “Domingo 01/06/2025” etc.
    """
    base = fetch_dashboard_data(user)

    hoje   = date.today()
    amanha = hoje + timedelta(days=1)
    dois_dias = hoje + timedelta(days=2)

    # ——— LISTA “ALL TASKS” ———
    all_tasks: List = TarefaService.list_for_user(user)

    # ——— FILTROS DE TAREFAS ———
    tasks_overdue = [
        t for t in all_tasks
        if t.due_date
           and t.due_date.date() < hoje
           and t.status == 'open'
    ]
    tasks_today = [
        t for t in all_tasks
        if t.due_date
           and t.due_date.date() == hoje
           and t.status == 'open'
    ]
    tasks_tomorrow = [
        t for t in all_tasks
        if t.due_date
           and t.due_date.date() == amanha
           and t.status == 'open'
    ]
    tasks_day_after_tomorrow = [
        t for t in all_tasks
        if t.due_date
           and t.due_date.date() == dois_dias
           and t.status == 'open'
    ]

    # ——— FILTROS DE PRAZOS ———
    open_deadlines = [p for p in base['prazos'] if getattr(p, 'status', 'open') == 'open']
    deadlines_overdue  = [p for p in open_deadlines if p.date < hoje]
    deadlines_today    = [p for p in open_deadlines if p.date == hoje]
    deadlines_tomorrow = [p for p in open_deadlines if p.date == amanha]
    deadlines_day_after_tomorrow = [  # <- este filtro garante “Depois de Amanhã”
        p for p in open_deadlines
        if p.date == dois_dias
    ]

    # ——— KPI COUNTS ———
    counts = {
        'tasks_overdue':      len(tasks_overdue),
        'tasks_today':        len(tasks_today),
        # não há card no topo para “tasks_day_after_tomorrow”
        'deadlines_today':    len(deadlines_today),
        'deadlines_overdue':  len(deadlines_overdue),
        'deadlines_tomorrow': len(deadlines_tomorrow),
        'assuntos_active':    len(base['assuntos']),
        # 'notifications':      NotificationService.count_unread(user.id),
    }

    # ——— DAY LABELS (ex.: “Domingo 01/06/2025”, “Segunda-Feira 02/06/2025”, “Terça-Feira 03/06/2025”) ———
    primeiro_do_mes = hoje.replace(day=1)
    map_semana = {
        0: "Segunda-Feira",
        1: "Terça-Feira",
        2: "Quarta-Feira",
        3: "Quinta-Feira",
        4: "Sexta-Feira",
        5: "Sábado",
        6: "Domingo",
    }
    day_labels: List[Dict[str, str]] = []
    for i in range(3):
        d = primeiro_do_mes + timedelta(days=i)
        nome_semana_pt = map_semana[d.weekday()]
        day_labels.append({
            'weekday': nome_semana_pt,
            'date':    d.strftime('%d/%m/%Y')
        })

    # ——— MONTAÇÃO DO DICIONÁRIO FINAL ———
    return {
        # datas de referência
        'hoje':    hoje,
        'amanha':  amanha,

        # listas de objetos (tarefas)
        'tasks_overdue':             tasks_overdue,
        'tasks_today':               tasks_today,
        'tasks_tomorrow':            tasks_tomorrow,
        'tasks_day_after_tomorrow':  tasks_day_after_tomorrow,

        # listas de objetos (prazos)
        'deadlines_overdue':             deadlines_overdue,
        'deadlines_today':               deadlines_today,
        'deadlines_tomorrow':            deadlines_tomorrow,
        'deadlines_day_after_tomorrow':  deadlines_day_after_tomorrow,

        # contagens para os KPI cards
        'counts': counts,

        # dados extras para tabelas detalhadas ou macros
        'assuntos':      base['assuntos'],
        'task_hours':    base['task_hours'],
        'prazo_hours':   base['prazo_hours'],
        'assunto_hours': base['assunto_hours'],

        # rótulos de dia para os “quadrados pretos”
        'day_labels':                 day_labels,
    }
