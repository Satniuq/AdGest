# app/accounting/routes.py

import logging
from io import StringIO
from datetime import datetime, date
from functools import wraps
from werkzeug.utils import secure_filename

from flask import (
    render_template, redirect, url_for,
    flash, request, jsonify, current_app,
)

from sqlalchemy import or_


from flask_login import login_required, current_user

from app.accounting import accounting
from app.accounting.forms import InvoiceForm, UploadCSVForm
from app.accounting.services import (
    DocumentoService,
    CsvService,
    DuplicateClientError,
    InvalidDocumentTypeError
)
from app.accounting.repositories import (
    DocumentoRepo,
    ClienteRepo,
    NotificationRepo,
    BillingNotaRepo
)
from app.accounting.models import DocumentoContabilistico
from app.billing.models import BillingNota
from app.clientes.models import Client

logger = logging.getLogger(__name__)


def parse_date_param(name):
    raw = request.args.get(name)
    if raw:
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            logger.warning(f"Invalid date format for {name}: {raw}")
    return None


def get_common_filters():
    return {
        'tipo':           request.args.get('tipo', ''),
        'data_emissao':   parse_date_param('data_emissao'),
        'advogado':       request.args.get('advogado', ''),
        'cliente_nome':   request.args.get('cliente', ''),
        'status':         request.args.get('status', ''),
        'dias_atraso':    request.args.get('dias_atraso', ''),
        'numero_cliente': request.args.get('numero_cliente', ''),
    }


def owner_required(model, id_arg='doc_id', param_name='doc'):
    def decorator(f):
        @wraps(f)
        def decorated_function(**kwargs):
            obj = model.query.get_or_404(kwargs.get(id_arg))
            if obj.user_id != current_user.id:
                flash("Sem permissão.", "danger")
                return redirect(url_for('accounting.manage_invoices'))
            kwargs[param_name] = obj
            kwargs.pop(id_arg, None)
            return f(**kwargs)
        return decorated_function
    return decorator


@accounting.context_processor
def inject_notifications_accounting():
    if current_user.is_authenticated:
        notifs = NotificationRepo.get_for_user(current_user)
        unread = sum(1 for n in notifs if not n.is_read)
        return dict(notifications=notifs, unread_count=unread)
    return dict(notifications=[], unread_count=0)


@accounting.route('/manage', methods=['GET'])
@login_required
def manage_invoices():
    # 1) Dois formulários distintos
    invoice_form = InvoiceForm()
    upload_form  = UploadCSVForm()

    # 2) Filtros e paginação
    filters     = get_common_filters()
    ordenar_por = request.args.get('ordenar_por', 'created_at_desc')
    page        = request.args.get('page', 1, type=int)
    per_page    = current_app.config.get('INVOICES_PER_PAGE', 20)

    # 3) Query com filtros e ordering
    q           = DocumentoRepo.query_for_manage(current_user)
    q           = DocumentoService.apply_filters_manage(q, filters)
    q           = DocumentoService.apply_ordering(q, ordenar_por)
    pagination  = q.paginate(page=page, per_page=per_page, error_out=False)

    # 4) Renderiza passando ambos os forms
    return render_template(
        'accounting/manage_invoices.html',
        invoices=      pagination.items,
        pagination=    pagination,
        invoice_form=  invoice_form,
        upload_form=   upload_form,
        filters=       filters,
        ordenar_por=   ordenar_por,
        today=         date.today()
    )

@accounting.route('/add_invoice', methods=['POST'])
@login_required
def add_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        try:
            DocumentoService.create_from_form(form, current_user)
            flash('Documento inserido com sucesso!', 'success')
            return redirect(url_for('accounting.manage_invoices'))
        except (DuplicateClientError, InvalidDocumentTypeError) as e:
            flash(str(e), 'danger')
        except Exception as e:
            logger.exception("Erro ao criar documento")
            flash(f"Ocorreu um erro inesperado: {str(e)}", 'danger')
    else:
        flash(f"Erros no formulário: {form.errors}", 'danger')
    return manage_invoices()


@accounting.route('/api/clientes')
@login_required
def api_clientes():
    term = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('CLIENTS_PER_PAGE', 20)
    pagination = ClienteRepo.search(term).paginate(page, per_page, False)
    results = [{'id': c.id, 'text': c.name} for c in pagination.items]
    return jsonify({
        'results': results,
        'pagination': {'more': pagination.has_next}
    })


@accounting.route('/upload_csv', methods=['GET', 'POST'])
@login_required
def upload_csv():
    form = UploadCSVForm()
    if form.validate_on_submit():
        file = form.csv_file.data
        filename = secure_filename(file.filename or '')
        if not filename.lower().endswith('.csv'):
            flash("Só são permitidos ficheiros .csv", "danger")
            return render_template('accounting/upload_csv.html', form=form)
        try:
            rows = CsvService.parse_csv(file)
            tmp = CsvService.save_tmp(rows, current_user)
            flash(f"{len(rows)} registros lidos com sucesso.", 'success')
            return redirect(url_for('accounting.preview_csv', tmp_id=tmp.id))
        except Exception:
            logger.exception("Erro ao processar CSV")
            flash(f"Erro ao processar CSV: {str(e)}", "danger")
    return render_template('accounting/upload_csv.html', form=form)


@accounting.route('/preview_csv/<int:tmp_id>', methods=['GET'])
@login_required
def preview_csv(tmp_id):
    tmp = CsvService.get_tmp(tmp_id, current_user)
    if not tmp:
        flash("CSV não encontrado ou acesso negado.", "warning")
        return redirect(url_for('accounting.upload_csv'))
    return render_template(
        'accounting/preview_csv.html',
        registros=tmp.data,
        tmp_id=tmp.id
    )


@accounting.route('/confirm_csv_import/<int:tmp_id>', methods=['POST'])
@login_required
def confirm_csv_import(tmp_id):
    try:
        count = CsvService.import_tmp(tmp_id, current_user)
        flash(f"{count} documentos importados com sucesso!", "success")
    except Exception:
        logger.exception("Erro na importação CSV")
        flash("Erro na importação dos documentos.", "danger")
    return redirect(url_for('accounting.manage_invoices'))


@accounting.route('/contabilidade_cliente/<int:client_id>')
@login_required
def contabilidade_cliente(client_id):
    # 1) Verifica permissão
    client = ClienteRepo.get(client_id)
    if not client or not (
        client.user_id == current_user.id or
        client.shared_with.filter_by(id=current_user.id).first() or
        client.shares.filter_by(user_id=current_user.id).first()
    ):
        flash("Sem permissão ou cliente não encontrado.", "danger")
        return redirect(url_for('accounting.manage_invoices'))

    # 2) Instancia o form de filtros (InvoiceForm possui os campos tipo, data_emissao e status que usamos no template)
    invoice_form = InvoiceForm(request.args)

    # 3) Query base para este cliente
    q = DocumentoRepo.query_for_client(current_user, client)

    # 4) Aplica os mesmos filtros de manage_invoices
    if invoice_form.tipo.data:
        q = q.filter(DocumentoContabilistico.tipo == invoice_form.tipo.data)
    if invoice_form.data_emissao.data:
        q = q.filter(DocumentoContabilistico.data_emissao == invoice_form.data_emissao.data)
    if invoice_form.status.data:
        q = q.filter(DocumentoContabilistico.status_cobranca == invoice_form.status.data)

    # 5) Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = q.order_by(DocumentoContabilistico.created_at.desc()) \
                  .paginate(page=page, per_page=per_page, error_out=False)
    invoices = pagination.items

    # 6) Separa em pagos e pendentes nesta página
    paid_invoices    = [inv for inv in invoices if inv.is_confirmed]
    pending_invoices = [inv for inv in invoices if not inv.is_confirmed]

    # 7) Dicionário de filtros para marcar os selects
    filters = {
        'tipo':         invoice_form.tipo.data or '',
        'data_emissao': invoice_form.data_emissao.data and invoice_form.data_emissao.data.isoformat() or '',
        'status':       invoice_form.status.data or ''
    }

    return render_template(
        'accounting/contabilidade_cliente.html',
        client=client,
        invoice_form=invoice_form,
        filters=filters,
        pagination=pagination,
        paid_invoices=paid_invoices,
        pending_invoices=pending_invoices,
        today=date.today()
    )

@accounting.route('/documento/alterar_status/<int:doc_id>', methods=['POST'])
@login_required
@owner_required(DocumentoContabilistico)
def alterar_status_documento(doc):
    novo = request.form.get('status')
    recibo = request.form.get('numero_recibo')
    doc.is_confirmed    = (novo == 'paga')
    doc.status_cobranca = novo
    # Se houver um recibo no form, grava sempre
    if recibo:
        doc.numero_recibo = recibo
    DocumentoRepo.save(doc)
    flash("Status atualizado!", "success")
    return redirect(
        url_for('accounting.contabilidade_cliente', client_id=doc.client_id)
    )


@accounting.route('/documento/edit/<int:doc_id>', methods=['GET', 'POST'])
@login_required
@owner_required(DocumentoContabilistico)
def edit_documento(doc):
    # 1) Instancia o formulário com o objeto para preencher 1:1
    form = InvoiceForm(obj=doc)

    # Pré-seleciona o cliente existente
    form.client_existing.data = doc.client

    # 2) Ajusta o query_factory para incluir notas pendentes OU já associadas
    existing_ids = [nota.id for nota in doc.notas]
    def notas_query():
        return (
            BillingNota.query
            .join(Client)
            .filter(
                Client.user_id == current_user.id,
                or_(
                    BillingNota.status == 'pendente',
                    BillingNota.id.in_(existing_ids)
                )
            )
            .order_by(BillingNota.created_at.desc())
        )
    form.notas.query_factory = notas_query

    # Pré-seleciona as notas já ligadas e o histórico
    form.notas.data     = list(doc.notas)
    form.historico.data = doc.details

    if form.validate_on_submit():
        # Atualiza tudo num único commit
        DocumentoService.update_from_form(doc, form)
        flash('Documento atualizado!', 'success')
        return redirect(
            url_for(
                'accounting.contabilidade_cliente',
                client_id=doc.client_id,
                modal=doc.id
            )
        )

    return render_template(
        'accounting/edit_documento.html',
        doc=doc,
        form=form
    )


@accounting.route('/relatorio_contabilidade')
@login_required
def relatorio_contabilidade():
    filters      = get_common_filters()
    ordenar_por  = request.args.get('ordenar_por', 'created_at_desc')
    page         = request.args.get('page', 1, type=int)
    per_page     = current_app.config.get('REPORT_PER_PAGE', 50)

    # Query + filtros + paginação
    q = DocumentoRepo.query_for_manage(current_user)
    q = DocumentoService.apply_filters_manage(q, filters)
    q = DocumentoService.apply_ordering(q, ordenar_por)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    docs       = pagination.items

    # Totais sobre TODOS os filtrados (q.all())
    all_docs     = q.all()
    total_valor  = sum(d.valor for d in all_docs)
    total_paid   = sum(
        d.valor for d in all_docs
        if getattr(d.status_cobranca, 'value', d.status_cobranca) == 'paga'
    )
    total_unpaid = total_valor - total_paid

    invoice_form = InvoiceForm()  # para ter choices no template

    return render_template(
        'accounting/relatorio_contabilidade.html',
        documentos=docs,
        pagination=pagination,
        total_valor=total_valor,
        total_paid=total_paid,
        total_unpaid=total_unpaid,
        filters=filters,
        ordenar_por=ordenar_por,
        invoice_form=invoice_form,
    )

@accounting.route('/documento/<int:doc_id>')
@login_required
def view_documento_por_id(doc_id):
    documento = DocumentoContabilistico.query.get_or_404(doc_id)
    return render_template(
        'billing/view_documento.html',
        documento=documento
    )