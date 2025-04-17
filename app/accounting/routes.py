import csv
import unicodedata
from io import StringIO
from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, session, make_response
from app.accounting import accounting
from app.accounting.forms import InvoiceForm, UploadCSVForm
from app.models import NotaHonorarios, Client, DocumentoContabilistico, Notification, ClientShare
from app import db
from flask_login import login_required, current_user
from sqlalchemy import func, or_, and_

@accounting.context_processor
def inject_notifications_accounting():
    if current_user.is_authenticated:
        notifs = Notification.query.filter_by(user_id=current_user.id)\
                                   .order_by(Notification.timestamp.desc()).all()
        unread = sum(1 for n in notifs if not n.is_read)
        return dict(notifications=notifs, unread_count=unread)
    return dict(notifications=[], unread_count=0)

@accounting.route('/manage', methods=['GET', 'POST'])
@login_required
def manage_invoices():
    form = InvoiceForm()
    
    accessible_numbers_subq = (
        db.session.query(Client.number_interno)
        .filter(
            or_(
                Client.user_id == current_user.id,
                Client.shared_with.any(id=current_user.id),
                Client.shares.any(ClientShare.user_id == current_user.id)
            )
        )
        .subquery()
    )

    # Filtra os documentos cujo cliente tenha um número interno presente na subquery
    query = DocumentoContabilistico.query.join(Client).filter(
        Client.number_interno.in_(accessible_numbers_subq)
    )

    # Parâmetros de filtro via GET:
    tipo = request.args.get('tipo', '')
    data_emissao = request.args.get('data_emissao', '')
    advogado = request.args.get('advogado', '')
    cliente_nome = request.args.get('cliente', '')
    status = request.args.get('status', '')
    dias_atraso = request.args.get('dias_atraso', '')
    numero_cliente = request.args.get('numero_cliente', '')
    ordenar_por = request.args.get('ordenar_por', 'created_at_desc')  # novo parâmetro

    if numero_cliente:
        query = query.filter(DocumentoContabilistico.numero_cliente.ilike(f"%{numero_cliente}%"))
    
    if tipo:
        query = query.filter(DocumentoContabilistico.tipo == tipo)
    if data_emissao:
        try:
            d = datetime.strptime(data_emissao, '%Y-%m-%d').date()
            query = query.filter(DocumentoContabilistico.created_at >= d)
        except ValueError:
            pass
    if advogado:
        query = query.filter(DocumentoContabilistico.advogado.ilike(f"%{advogado}%"))
    
    if cliente_nome:
        query = query.join(Client).filter(Client.name.ilike(f"%{cliente_nome}%"))
    if status:
        if status == 'pendente':
            query = query.filter(DocumentoContabilistico.status_cobranca.in_([
                'pendente', 'tentativa_cobranca', 'em_tribunal', 'incobravel'
            ]))
        else:
            query = query.filter(DocumentoContabilistico.status_cobranca == status)
    if dias_atraso:
        try:
            dias = int(dias_atraso)
            today = date.today()
            query = query.filter(func.coalesce(DocumentoContabilistico.data_vencimento, DocumentoContabilistico.data_emissao) != None)
            query = query.filter(
                func.julianday(today) - func.julianday(
                    func.coalesce(DocumentoContabilistico.data_vencimento, DocumentoContabilistico.data_emissao)
                ) <= dias
            )
        except ValueError:
            pass

    # Ordenação baseada no parâmetro "ordenar_por"
    if ordenar_por == 'data_emissao_asc':
        query = query.order_by(DocumentoContabilistico.data_emissao.asc())
    elif ordenar_por == 'data_emissao_desc':
        query = query.order_by(DocumentoContabilistico.data_emissao.desc())
    elif ordenar_por == 'data_vencimento_asc':
        query = query.order_by(DocumentoContabilistico.data_vencimento.asc())
    elif ordenar_por == 'data_vencimento_desc':
        query = query.order_by(DocumentoContabilistico.data_vencimento.desc())
    elif ordenar_por == 'valor_asc':
        query = query.order_by(DocumentoContabilistico.valor.asc())
    elif ordenar_por == 'valor_desc':
        query = query.order_by(DocumentoContabilistico.valor.desc())
    else:
        query = query.order_by(DocumentoContabilistico.created_at.desc())
    
    invoices = query.all()
    
    return render_template('accounting/manage_invoices.html', invoices=invoices, form=form, today=date.today(), ordenar_por=ordenar_por)


@accounting.route('/add_invoice', methods=['POST'])
@login_required
def add_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        # Seleciona ou cria o cliente
        if form.client_existing.data:
            client = form.client_existing.data
        else:
            client_name = form.client_new.data.strip()
            client = Client.query.filter_by(user_id=current_user.id, name=client_name).first()
            if client:
                flash("Cliente já existente. Por favor, selecione-o na lista.", "danger")
                return redirect(url_for('accounting.manage_invoices'))
            else:
                client = Client(
                    user_id=current_user.id,
                    name=client_name
                )
                db.session.add(client)
                db.session.commit()  # Para gerar client.id

        # Apenas cria DocumentoContabilistico para tipos permitidos na inserção
        if form.tipo.data in ['fatura', 'despesa']:
            doc = DocumentoContabilistico(
                user_id=current_user.id,
                client_id=client.id,
                numero=form.numero.data,
                created_at=form.data_emissao.data,
                advogado=form.advogado.data,
                data_emissao=form.data_emissao.data,
                details=form.historico.data,
                valor=form.valor.data,
                is_confirmed=(form.status.data == 'paga'),
                tipo=form.tipo.data,
                data_vencimento=form.data_vencimento.data,
                # Novo atributo: número de cliente, obtido do cliente (pode ser None se não informado)
                numero_cliente=client.number_interno
            )
            db.session.add(doc)
        else:
            flash("Tipo de documento inválido.", "danger")
            return redirect(url_for('accounting.manage_invoices'))
        db.session.commit()

        flash('Documento inserido com sucesso!', 'success')
        return redirect(url_for('accounting.manage_invoices'))
    else:
        flash('Erro na validação da fatura.', 'danger')
        return redirect(url_for('accounting.manage_invoices'))

# Função para normalizar os cabeçalhos: converte para minúsculas e remove acentos
def normalize_header(header):
    header = header.strip().lower()
    header = unicodedata.normalize('NFKD', header).encode('ASCII', 'ignore').decode('utf-8')
    return header

# Função para tentar converter datas em vários formatos
def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

@accounting.route('/upload_csv', methods=['GET', 'POST'])
@login_required
def upload_csv():
    form = UploadCSVForm()
    if form.validate_on_submit():
        file = form.csv_file.data
        try:
            # Lê uma amostra do arquivo para detectar o delimitador
            sample = file.read(1024).decode('utf-8')
            file.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            stream = StringIO(file.read().decode('utf-8'))
            reader = csv.DictReader(stream, dialect=dialect)
            
            # Normaliza os cabeçalhos e remove espaços extras dos valores
            registros = []
            for row in reader:
                normalized_row = {normalize_header(k): (v.strip() if v else v) for k, v in row.items()}
                registros.append(normalized_row)
            
            flash(f"{len(registros)} registros foram lidos com sucesso.", "success")
            # Armazena os registros na sessão para a pré-visualização
            session['csv_registros'] = registros
            return redirect(url_for('accounting.preview_csv'))
        except Exception as e:
            flash("Erro ao processar o arquivo: " + str(e), "danger")
    return render_template('accounting/upload_csv.html', form=form)

@accounting.route('/preview_csv', methods=['GET', 'POST'])
@login_required
def preview_csv():
    registros = session.get('csv_registros', [])
    if not registros:
        flash("Nenhum registro para pré-visualizar. Importe um arquivo primeiro.", "warning")
        return redirect(url_for('accounting.upload_csv'))

    errors = []
    from app.models import Client
    # Verificações para cada registro
    for idx, row in enumerate(registros, start=1):
        # Usa a chave normalizada: pode ser 'client' ou 'cliente'
        client_name = (row.get('client') or row.get('cliente') or '').strip()
        numero_cliente = (row.get('numero_cliente') or '').strip()
        if not client_name:
            errors.append(f"Linha {idx}: Nome do cliente está vazio.")
            continue
        
        # Busca pelo cliente pelo nome e pelo número (se informado)
        existing_client_by_name = Client.query.filter_by(name=client_name, user_id=current_user.id).first()
        existing_client_by_num = None
        if numero_cliente:
            existing_client_by_num = Client.query.filter_by(number_interno=numero_cliente, user_id=current_user.id).first()
        
        # Se o cliente já existe pelo nome e no banco já possui número diferente do CSV, erro
        if existing_client_by_name and numero_cliente:
            if existing_client_by_name.number_interno and existing_client_by_name.number_interno != numero_cliente:
                errors.append(f"Linha {idx}: Cliente '{client_name}' já existe com número '{existing_client_by_name.number_interno}', mas o CSV informa '{numero_cliente}'.")
        # Se o número já existe associado a outro cliente (nome diferente), erro
        if existing_client_by_num and existing_client_by_num.name.lower() != client_name.lower():
            errors.append(f"Linha {idx}: O número de cliente '{numero_cliente}' já pertence a '{existing_client_by_num.name}', mas o CSV indica '{client_name}'.")
    
    if request.method == 'POST':
        if errors:
            flash("Existem erros que precisam ser corrigidos antes de confirmar a importação.", "danger")
        else:
            # Em vez de redirecionar, renderize um template intermediário para confirmação
            return render_template('accounting/confirm_csv_import.html', registros=registros)
    
    return render_template('accounting/preview_csv.html', registros=registros, errors=errors)

@accounting.route('/confirm_csv_import', methods=['POST'])
@login_required
def confirm_csv_import():
    from app.models import DocumentoContabilistico, Client
    registros = session.get('csv_registros', [])
    if not registros:
        flash("Não há registros na sessão para importar.", "danger")
        return redirect(url_for('accounting.upload_csv'))
    # Remove os registros da sessão para evitar reimportação acidental
    session.pop('csv_registros', None)

    imported_count = 0
    try:
        for row in registros:
            # Usa a chave 'client' (ou 'cliente') normalizada para obter o nome do cliente
            client_name = row.get('client') or row.get('cliente')
            client_name = client_name.strip() if client_name else ''
            if not client_name:
                continue

            # Pega o número do cliente do CSV
            num_cliente = row.get('numero_cliente')
            
            # Procura o cliente pelo nome e usuário
            client = Client.query.filter_by(name=client_name, user_id=current_user.id).first()
            if not client:
                # Cria o cliente, atribuindo também o número, se fornecido
                client = Client(user_id=current_user.id, name=client_name, number_interno=num_cliente)
                db.session.add(client)
                db.session.flush()  # Gera client.id
            else:
                # Se o cliente já existe, atualiza o número se ele estiver vazio e o CSV fornecer um valor
                if num_cliente and not client.number_interno:
                    client.number_interno = num_cliente

            # Converte as datas (tenta vários formatos)
            data_emissao = parse_date(row.get('data_emissao'))
            data_vencimento = parse_date(row.get('data_vencimento'))

            try:
                valor = float(row.get('valor', '0'))
            except Exception:
                valor = 0.0

            doc = DocumentoContabilistico(
                user_id=current_user.id,
                client_id=client.id,
                numero=row.get('numero'),
                data_emissao=data_emissao,
                data_vencimento=data_vencimento,
                tipo=row.get('tipo', 'fatura'),  # Deve ser "fatura" ou "despesa"
                valor=valor,
                advogado=row.get('advogado'),
                details=row.get('historico'),
                status_cobranca=row.get('status', 'pendente'),
                numero_recibo=row.get('numero_recibo'),
                numero_cliente=row.get('numero_cliente'),
                is_confirmed=(row.get('status') == 'paga')
            )
            db.session.add(doc)
            imported_count += 1
        db.session.commit()
        flash(f"{imported_count} documentos importados com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao importar: {e}", "danger")
    return redirect(url_for('accounting.manage_invoices'))

@accounting.route('/contabilidade_cliente/<int:client_id>') 
@login_required
def contabilidade_cliente(client_id):
    client = Client.query.get_or_404(client_id)
    
    # Se o usuário logado for o dono, traz todos os documentos vinculados ao número interno
    if client.user_id == current_user.id:
        contabil_docs = (
            DocumentoContabilistico.query
            .join(Client)
            .filter(Client.number_interno == client.number_interno)
            .order_by(DocumentoContabilistico.created_at.desc())
            .all()
        )
    else:
        contabil_docs = (
            DocumentoContabilistico.query
            .join(Client)
            .filter(
                Client.number_interno == client.number_interno,
                or_(
                    DocumentoContabilistico.user_id == current_user.id,
                    DocumentoContabilistico.client.has(Client.shares.any(ClientShare.user_id == current_user.id)),
                    DocumentoContabilistico.client.has(Client.shared_with.any(id=current_user.id))
                )
            )
            .order_by(DocumentoContabilistico.created_at.desc())
            .all()
        )
    
    paid_docs = [doc for doc in contabil_docs if doc.is_confirmed]
    pending_docs = [doc for doc in contabil_docs if not doc.is_confirmed]
    
    return render_template('accounting/contabilidade_cliente.html',
                           client=client,
                           paid_docs=paid_docs,
                           pending_docs=pending_docs,
                           today=date.today())


@accounting.route('/documento/alterar_status/<int:doc_id>', methods=['POST'])
@login_required
def alterar_status_documento(doc_id):
    doc = DocumentoContabilistico.query.get_or_404(doc_id)

    if doc.user_id != current_user.id:
        flash("Não tens permissão para alterar este documento.", "danger")
        return redirect(url_for('accounting.contabilidade_cliente', client_id=doc.client_id))

    novo_status = request.form.get('status')
    numero_recibo = request.form.get('numero_recibo')

    if novo_status == 'paga':
        doc.is_confirmed = True
        doc.status_cobranca = 'paga'
        if numero_recibo:
            doc.numero_recibo = numero_recibo
    else:
        doc.is_confirmed = False
        doc.status_cobranca = novo_status

    db.session.commit()
    flash("Status do documento atualizado!", "success")
    return redirect(url_for('accounting.contabilidade_cliente', client_id=doc.client_id))

@accounting.route('/documento/edit/<int:doc_id>', methods=['GET', 'POST'])
@login_required
def edit_documento(doc_id):
    doc = DocumentoContabilistico.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        flash("Não tens permissão para editar este documento.", "danger")
        return redirect(url_for('main.clientes'))
    
    form = InvoiceForm(obj=doc)
    
    # Se o documento já tem um client, defina no form.client_existing
    form.client_existing.data = doc.client  # Ajusta o QuerySelectField para o cliente atual

    if request.method == 'POST':
        if form.validate_on_submit():
            doc.numero = form.numero.data
            doc.tipo = form.tipo.data
            doc.data_emissao = form.data_emissao.data
            doc.data_vencimento = form.data_vencimento.data
            doc.valor = form.valor.data
            doc.advogado = form.advogado.data
            doc.status_cobranca = form.status.data
            doc.details = form.historico.data
            db.session.commit()
            flash("Documento atualizado com sucesso!", "success")
            return redirect(url_for('accounting.contabilidade_cliente', client_id=doc.client_id, modal=doc.id))
        else:
            flash(f"Erro ao validar o formulário: {form.errors}", "danger")
    return render_template('accounting/edit_documento.html', doc=doc, form=form)

@accounting.route('/relatorio_contabilidade')
@login_required
def relatorio_contabilidade():
    # Captura os mesmos filtros enviados por GET (como no manage_invoices)
    tipo = request.args.get('tipo', '')
    data_emissao = request.args.get('data_emissao', '')
    advogado = request.args.get('advogado', '')
    cliente_nome = request.args.get('cliente', '')
    status = request.args.get('status', '')
    dias_atraso = request.args.get('dias_atraso', '')
    numero_cliente = request.args.get('numero_cliente', '')
    ordenar_por = request.args.get('ordenar_por', 'created_at_desc')
    
    query = DocumentoContabilistico.query.filter_by(user_id=current_user.id)
    
    if numero_cliente:
        query = query.filter(DocumentoContabilistico.numero_cliente.ilike(f"%{numero_cliente}%"))
    if tipo:
        query = query.filter(DocumentoContabilistico.tipo == tipo)
    if data_emissao:
        try:
            d = datetime.strptime(data_emissao, '%Y-%m-%d').date()
            query = query.filter(DocumentoContabilistico.created_at >= d)
        except ValueError:
            pass
    if advogado:
        query = query.filter(DocumentoContabilistico.advogado.ilike(f"%{advogado}%"))
    if cliente_nome:
        query = query.join(Client).filter(Client.name.ilike(f"%{cliente_nome}%"))
    if status:
        if status == 'pendente':
            query = query.filter(DocumentoContabilistico.status_cobranca.in_([
                'pendente', 'tentativa_cobranca', 'em_tribunal', 'incobravel'
            ]))
        else:
            query = query.filter(DocumentoContabilistico.status_cobranca == status)
    if dias_atraso:
        try:
            dias = int(dias_atraso)
            today = date.today()
            query = query.filter(func.coalesce(DocumentoContabilistico.data_vencimento, DocumentoContabilistico.data_emissao) != None)
            query = query.filter(
                func.julianday(today) - func.julianday(
                    func.coalesce(DocumentoContabilistico.data_vencimento, DocumentoContabilistico.data_emissao)
                ) <= dias
            )
        except ValueError:
            pass

    if ordenar_por == 'data_emissao_asc':
        query = query.order_by(DocumentoContabilistico.data_emissao.asc())
    elif ordenar_por == 'data_emissao_desc':
        query = query.order_by(DocumentoContabilistico.data_emissao.desc())
    elif ordenar_por == 'data_vencimento_asc':
        query = query.order_by(DocumentoContabilistico.data_vencimento.asc())
    elif ordenar_por == 'data_vencimento_desc':
        query = query.order_by(DocumentoContabilistico.data_vencimento.desc())
    elif ordenar_por == 'valor_asc':
        query = query.order_by(DocumentoContabilistico.valor.asc())
    elif ordenar_por == 'valor_desc':
        query = query.order_by(DocumentoContabilistico.valor.desc())
    else:
        query = query.order_by(DocumentoContabilistico.created_at.desc())
    
    documentos = query.all()
    
    total_valor   = sum(doc.valor for doc in documentos)
    total_paid    = sum(doc.valor for doc in documentos if doc.status_cobranca == 'paga')
    total_unpaid  = sum(doc.valor for doc in documentos if doc.status_cobranca != 'paga')
    
    # Passa também os filtros aplicados para exibir no relatório
    filters = request.args
    
    return render_template('accounting/relatorio_contabilidade.html',
                           documentos=documentos,
                           total_valor=total_valor,
                           total_paid=total_paid,
                           total_unpaid=total_unpaid,
                           filters=filters)


