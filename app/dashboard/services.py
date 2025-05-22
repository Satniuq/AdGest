# app/dashboard/services.py

from datetime import date, timedelta
from typing import Dict, Any, List

from app.assuntos.services import AssuntoService
from app.prazos.services import PrazoService
from app.tarefas.services import TarefaService
# se usares notificações:
# from app.notifications.services import NotificationService

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

    # ← Aqui é fundamental devolver o dict
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
      - listas de tarefas (overdue, today, tomorrow)
      - listas de prazos (today, tomorrow)
      - contagens para KPI cards
    """
    base = fetch_dashboard_data(user)

    hoje   = date.today()
    amanha = hoje + timedelta(days=1)

    # achata todas as tarefas numa lista
    all_tasks: List = TarefaService.list_for_user(user)

    # filtra por datas/status
    tasks_overdue   = [
    t for t in all_tasks
    if t.due_date
       and t.due_date.date() < hoje
       and t.status == 'open'
    ]
    tasks_today     = [
        t for t in all_tasks
        if t.due_date
        and t.due_date.date() == hoje
        and t.status == 'open'
    ]
    tasks_tomorrow  = [
        t for t in all_tasks
        if t.due_date
        and t.due_date.date() == amanha
        and t.status == 'open'
    ]
    # só prazos “open”
    open_deadlines = [p for p in base['prazos'] if getattr(p, 'status', 'open') == 'open']
    deadlines_overdue  = [p for p in open_deadlines if p.date < hoje]
    deadlines_today    = [p for p in open_deadlines if p.date == hoje]
    deadlines_tomorrow = [p for p in open_deadlines if p.date == amanha]

    # KPI counts
    counts = {
        'tasks_overdue':      len(tasks_overdue),
        'tasks_today':        len(tasks_today),
        'deadlines_today':    len(deadlines_today),
        'deadlines_overdue':  len(deadlines_overdue),
        'deadlines_tomorrow': len(deadlines_tomorrow),
        'assuntos_active':    len(base['assuntos']),
        # 'notifications':      NotificationService.count_unread(user.id),
    }

    return {
        # datas de referência
        'hoje':    hoje,
        'amanha':  amanha,

        # listas de objetos
        'tasks_overdue':      tasks_overdue,
        'tasks_today':        tasks_today,
        'tasks_tomorrow':     tasks_tomorrow,

        'deadlines_overdue':  (deadlines_overdue),
        'deadlines_today':    deadlines_today,
        'deadlines_tomorrow': deadlines_tomorrow,

        # contagens para os KPI cards
        'counts': counts,

        # dados adicionais para macros ou tabelas detalhadas
        'assuntos':      base['assuntos'],
        'task_hours':    base['task_hours'],
        'prazo_hours':   base['prazo_hours'],
        'assunto_hours': base['assunto_hours'],
    }
