# app/dashboard_prazos/routes.py

from flask import render_template, request, jsonify, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm

from app.prazos.services    import PrazoService
from app.processos.services import ProcessoService
from app.prazos.forms       import AddPrazoHoursForm
from app.clientes.models    import Client
from app.processos.models   import CaseType, Phase, PracticeArea, Court
from app.prazos.models      import DeadlineType

from app.dashboard_prazos import dashboard_prazos_bp

class DummyForm(FlaskForm):
    """Apenas para gerar CSRF token"""

@dashboard_prazos_bp.route('/', methods=['GET'])
@login_required
def manage():
    # forms usados no dashboard
    add_hours_form = AddPrazoHoursForm()
    csrf_form      = DummyForm()

    # qual aba estamos: 'prazos' ou 'processos'
    mode = request.args.get('mode', 'processos')

    # filtros comuns
    client_id   = request.args.get('client_id',   type=int)
    external_id = request.args.get('external_id', type=str, default='')

    # filtros específicos
    type_id          = request.args.get('type_id',           type=int)  # prazos
    case_type_id     = request.args.get('case_type_id',      type=int)  # processos
    phase_id         = request.args.get('phase_id',          type=int)
    practice_area_id = request.args.get('practice_area_id',  type=int)
    court_id         = request.args.get('court_id',          type=int)
    status           = request.args.get('status',            type=str, default='')

    # captura 'sort' de acordo com o modo
    if mode == 'prazos':
        # ordenação por data limite: nearest (asc) ou farthest (desc)
        sort = request.args.get('sort', 'nearest')
    else:
        # ordenação por data de abertura: desc (mais recentes) ou asc (mais antigos)
        sort = request.args.get('sort', 'desc')

    # dropdowns para os filtros
    clients    = Client.query.order_by(Client.name).all()
    types      = DeadlineType.query.order_by(DeadlineType.name).all()
    case_types = CaseType.query.order_by(CaseType.name).all()
    phases     = Phase.query.filter_by(case_type_id=case_type_id).all() if case_type_id else []
    areas      = PracticeArea.query.order_by(PracticeArea.name).all()
    courts     = Court.query.order_by(Court.name).all()

    # prepara as listas de exibição
    if mode == 'processos':
        # lista de processos
        processos = ProcessoService.list_for_user(
            user_id=current_user.id,
            client_id=client_id,
            case_type_id=case_type_id,
            phase_id=phase_id,
            practice_area_id=practice_area_id,
            court_id=court_id,
            status=status or None
        )
        # filtra pelo número externo (partial match)
        if external_id:
            processos = [
                pr for pr in processos
                if external_id.lower() in (pr.external_id or '').lower()
            ]
        # ordena por data de abertura
        processos.sort(
            key=lambda pr: pr.opened_at,
            reverse=(sort == 'desc')
        )
        prazos = []
    else:
        # lista de prazos
        prazos = PrazoService.list_for_user(
            user_id=current_user.id,
            type_id=type_id,
            client_id=client_id,
            case_type_id=case_type_id,
            phase_id=phase_id,
            practice_area_id=practice_area_id,
            court_id=court_id,
            status=status or None
        )
        # filtra pelo número externo do processo
        if external_id:
            prazos = [
                p for p in prazos
                if external_id.lower() in (p.processo.external_id or '').lower()
            ]
        # ordena por data limite
        prazos.sort(
            key=lambda p: p.date,
            reverse=(sort == 'farthest')
        )
        processos = []
        

    return render_template(
        'manage.html',
        mode=mode,

        # forms
        add_hours_form=add_hours_form,
        csrf_form=csrf_form,

        # valores atuais dos filtros
        client_id=client_id,
        external_id=external_id,
        sort=sort,
        type_id=type_id,
        case_type_id=case_type_id,
        phase_id=phase_id,
        practice_area_id=practice_area_id,
        court_id=court_id,
        status=status,

        # opções de dropdown
        clients=clients,
        types=types,
        case_types=case_types,
        phases=phases,
        areas=areas,
        courts=courts,

        # dados a exibir
        prazos=prazos,
        processos=processos
    )

@dashboard_prazos_bp.route('/ajax/phases/<int:case_type_id>', methods=['GET'])
@login_required
def ajax_phases(case_type_id):
    phases = ProcessoService.list_phases(case_type_id)
    return jsonify([{'id': ph.id, 'name': ph.name} for ph in phases])
