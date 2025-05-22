# seed_prazos.py

from datetime import datetime, date, timedelta
from app import create_app, db
from app.auth.models       import User
from app.clientes.models   import Client
from app.processos.models  import (
    CaseType, Phase,
    PracticeArea, Court,
    Tag, Processo
)
from app.prazos.models     import (
    DeadlineType, RecurrenceRule,
    PrazoJudicial, PrazoBillingItem,
    PrazoHistory
)

app = create_app()
with app.app_context():
    # 1) Cria as tabelas (se ainda não existirem)
    db.create_all()

    # 2) Usa o admin já existente
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        raise RuntimeError("Usuário 'admin' não encontrado. Crie-o antes de rodar este seed.")

    # 3) Clientes de exemplo
    clientes = []
    for name, interno in [
        ('Alpha Ltda', 'CLI-100'),
        ('Beta S.A.',   'CLI-200')
    ]:
        cli = Client.query.filter_by(name=name).first()
        if not cli:
            cli = Client(
                user_id=admin.id,
                name=name,
                number_interno=interno,
                nif='000000000',
                address='Rua Exemplo, 123',
                email=f'{name.lower().replace(" ", "")}@ex.com',
                telephone='919999999'
            )
            db.session.add(cli)
            db.session.flush()
        clientes.append(cli)

    # 4) CaseTypes e suas Phases
    case_types_data = {
        'Civil': [
            'Petição inicial',
            'Citação',
            'Contestação',
            'Reconvenção',
            'Impugnação de documentos',
            'Réplica',
            'Audiência prévia',
            'Despacho saneador',
            'Julgamento',
            'Sentença',
            'Recurso',
            'Acórdão'
        ],
        'Execuções': [
            'Requerimento exeutivo',
            'Penhora',
            'Citação',
            'Embargos de executado',
            'Contestação a embargos',
            'Oposição à penhora',
            'Julgamento',
            'Sentença',
            'Recurso',
            'Acórdão',
            'Venda',
            'Entrega de resultados',
        ],
        'Insolvência': [
            'Pedido de insolvência',
            'Reclamação de créditos',
            'Liquidação',
            'Rateio',
            'Encerramento',
            'Exoneração passivo restante',
        ],
        'Crime': [
            'Queixa crime',
            'Despacho arquivamento',
            'Despacho acusação',
            'Acusação particular',
            'Julgamento',
            'Sentença'
        ],
        'Laboral': [
            'Petição inicial',
            'Audiência de partes',
            'Contestação',
            'Julgamento',
            'Sentença'
        ],
        'Administrativo': [
            'Reclamação',
            'Recurso hierárquico',
            'Recurso judicial',
            'Julgamento',
            'Sentença'
        ],
        'Contraordenação': [
            'Notificação de contraordenação',
            'Defesa',
            'Decisão final',
            'Impugnação judicial',
            'Julgamento',
            'Sentença'
        ],
        'Injunção': [
            'Requerimento injuntivo',
            'Notificação',
            'Título executivo',
            'Oposição',
            'AECOP'
        ],
        'NJA': [
            'Requerimento inicial',
            'Despacho',
            'Notificação efetuada',
            'Notificação frustrada'
        ]
    }
    for ct_name, phase_names in case_types_data.items():
        ct = CaseType.query.filter_by(name=ct_name).first()
        if not ct:
            ct = CaseType(name=ct_name)
            db.session.add(ct)
            db.session.flush()
        # cria fases ordenadas
        for idx, ph_name in enumerate(phase_names, start=1):
            ph = Phase.query.filter_by(case_type_id=ct.id, name=ph_name).first()
            if not ph:
                ph = Phase(
                    case_type_id=ct.id,
                    name=ph_name,
                    sort_order=idx,
                    description=f'Fase "{ph_name}" do caso {ct_name}'
                )
                db.session.add(ph)

    # 5) PracticeAreas
    for pa_name in ['Civil', 'Crime', 'Trabalho', 'Comércio', 'Administrativo']: 
        pa = PracticeArea.query.filter_by(name=pa_name).first()
        if not pa:
            pa = PracticeArea(name=pa_name, description=f'Área {pa_name}')
            db.session.add(pa)

    # 6) Courts
    for court_name in ['Juízo Cívil', 'Juízo de Família e Menores', 'Juizo de Trabalho', 'Juízo de Execuções', 'Juízo de Comércio','Administrativo e Fiscal',]:
        cr = Court.query.filter_by(name=court_name).first()
        if not cr:
            cr = Court(name=court_name, address=f'Endereço da {court_name}')
            db.session.add(cr)

    # 7) Tags
    for tag_name in ['Urgente', 'Revisar', 'Importante']:
        t = Tag.query.filter_by(name=tag_name).first()
        if not t:
            t = Tag(name=tag_name)
            db.session.add(t)

    # 8) DeadlineTypes
    for name, desc in [
        ('Petição',   'Envio da petição inicial'),
        ('Contestação', 'Prazo para contestar'),
        ('Impugna Docs', 'Prazo para impugnar documentos'),
        ('Réplica', 'Prazo para réplica'),
        ('Audiência', 'Audiência judicial'),
        ('Recurso',   'Prazo para interpor recurso'),
        ('Sentença',  'Prazo para sentença'),
        ('Acórdão',   'Prazo para acórdão'),
        ('Queixa',   'Prazo para queixa crime'),
        ('Defesa', 'Prazo para defesa'),
        ('Impugnação', 'Prazo para impugnação'),
        ('Notificação', 'Prazo geral de notificação'),
    ]:
        dt = DeadlineType.query.filter_by(name=name).first()
        if not dt:
            dt = DeadlineType(name=name, description=desc)
            db.session.add(dt)

    # 9) RecurrenceRules
    for name, rule in [
        ('Diária',  'FREQ=DAILY'),
        ('Semanal', 'FREQ=WEEKLY'),
        ('Mensal',  'FREQ=MONTHLY'),
    ]:
        rr = RecurrenceRule.query.filter_by(name=name).first()
        if not rr:
            rr = RecurrenceRule(name=name, rrule=rule)
            db.session.add(rr)

    db.session.commit()

    # 10) Processos de exemplo (um por cliente)
    cts    = {ct.name: ct for ct in CaseType.query.all()}
    pas    = {pa.name: pa for pa in PracticeArea.query.all()}
    courts = {c.name: c   for c in Court.query.all()}
    tags   = {t.name: t   for t in Tag.query.all()}

    for idx, cliente in enumerate(clientes, start=1):
        ext = f'P-2025-{idx:04d}'
        proc = Processo.query.filter_by(external_id=ext).first()
        if not proc:
            # atribui sempre o CaseType "Cívil" e sua primeira fase
            ct = cts['Civil']
            ph = Phase.query.filter_by(case_type_id=ct.id)\
                            .order_by(Phase.sort_order).first()
            proc = Processo(
                external_id      = ext,
                case_type_id     = ct.id,
                phase_id         = ph.id if ph else None,
                practice_area_id = pas['Civil'].id,
                court_id         = courts['Juízo Cívil'].id,
                lead_attorney_id = admin.id,
                client_id        = cliente.id,
                status           = 'open',
                opened_at        = datetime.utcnow()
            )
            # tags de exemplo
            proc.tags = [tags['Urgente'], tags['Importante']]
            db.session.add(proc)

    db.session.commit()

    # ——— 11) Prazos judiciais de exemplo ———
    dts = {dt.name: dt for dt in DeadlineType.query.all()}
    rrs = {rr.name: rr for rr in RecurrenceRule.query.all()}
    # cria os prazos
    for proc in Processo.query.all():
        pj = PrazoJudicial.query.filter_by(processo_id=proc.id).first()
        if not pj:
            pj = PrazoJudicial(
                processo_id   = proc.id,
                owner_id       = admin.id,
                client_id      = proc.client_id,
                type_id        = dts['Audiência'].id,
                recur_rule_id  = rrs['Semanal'].id,
                date           = date.today() + timedelta(days=7),
                description    = 'Audiência preliminar',
                comments       = 'Trazer documentos',
                hours_spent    = 1.5,
                status         = 'open'
            )
            db.session.add(pj)
    db.session.commit()

    # ——— 12) Cria um histórico mínimo e um billing item de exemplo ———
    for pj in PrazoJudicial.query.all():
        # 12.a) se não tiver histórico, cria um entry "seed"
        if pj.history.count() == 0:
            snapshot = {}
            for col in pj.__table__.columns:
                val = getattr(pj, col.name)
                snapshot[col.name] = val.isoformat() if hasattr(val, 'isoformat') else val
            seed_hist = PrazoHistory(
                prazo_id    = pj.id,
                change_type = 'seed',
                changed_at  = datetime.utcnow(),
                changed_by  = admin.id,
                snapshot    = snapshot,
                detail      = 'Seed history'
            )
            db.session.add(seed_hist)
            db.session.flush()   # garante seed_hist.id
        else:
            seed_hist = pj.history.first()

        # 12.b) se não existir billing item, cria um de 0.5h ligado a esse history
        exists = PrazoBillingItem.query.filter_by(history_id=seed_hist.id).first()
        if not exists:
            item = PrazoBillingItem(
                prazo_id        = pj.id,
                history_id      = seed_hist.id,
                hours           = 0.5,
                description     = 'Teste de billing seed',
                created_by      = admin.id
            )
            db.session.add(item)

    db.session.commit()
    print('✅ Banco seedado com CaseTypes, Phases, Processos, Prazos, Históricos e BillingItems!')
