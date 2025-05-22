# app/billing/routes.py

from flask import render_template, request
from flask_login import login_required
from app.billing import billing_bp
from app.billing.forms import NotaSearchForm
from app.billing.services import BillingService
from app.billing.models import BillingNota
from app.accounting.models import DocumentoContabilistico

@billing_bp.route('/', methods=['GET','POST'])
@login_required
def list_notas():
    form = NotaSearchForm(request.args)
    notas = BillingService.search_notas(
        source_type = form.source_type.data or None,
        date_from   = form.date_from.data,
        date_to     = form.date_to.data
    )
    return render_template('billing/list.html', form=form, notas=notas)

@billing_bp.route('/<int:nota_id>', methods=['GET'])
@login_required
def view_nota(nota_id):
    nota  = BillingService.get_nota(nota_id)
    return render_template('billing/view.html', nota=nota)

@billing_bp.route('/nota/<int:nota_id>/documento/<int:doc_id>')
@login_required
def view_documento(nota_id, doc_id):
    nota = BillingNota.query.get_or_404(nota_id)
    # tenta buscar o documento entre os associados
    doc = next((d for d in nota.documentos_contabilisticos if d.id == doc_id), None)
    if not doc:
        # 404 se não pertencer à nota
        abort(404)
    return render_template(
        'billing/view_documento.html',
        nota=nota,
        documento=doc
    )

@billing_bp.route('/nota/<int:nota_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_nota(nota_id):
    nota = BillingNota.query.get_or_404(nota_id)

    # Só permita edição em status adequados, ex.: draft ou pending
    if nota.status not in ('draft', 'pending'):
        flash('Esta nota não pode ser editada no estado atual.', 'warning')
        return redirect(url_for('billing.view_nota', nota_id=nota.id))

    form = NotaHonorariosForm(obj=nota)
    if form.validate_on_submit():
        # Atualiza campos editáveis
        nota.cliente_id     = form.cliente.data.id
        nota.total_hours    = form.total_hours.data
        nota.status         = form.status.data
        # (adicione aqui outros campos que queira permitir editar)

        db.session.commit()
        flash(f'Nota #{nota.id} atualizada com sucesso.', 'success')
        return redirect(url_for('billing.view_nota', nota_id=nota.id))

    # Pré-popula o formulário com dados existentes
    return render_template(
        'billing/edit_nota.html',
        nota=nota,
        form=form
    )