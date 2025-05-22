# app/accounting/services.py

from datetime import datetime
from decimal import Decimal
from io import StringIO
import csv
import unicodedata

from app import db
from app.accounting.models import DocumentoContabilistico, TmpDocumento
from app.accounting.repositories import (
    DocumentoRepo, ClienteRepo,
    BillingNotaRepo, TmpDocumentoRepo
)
from app.clientes.models import Client


class DuplicateClientError(Exception): pass
class InvalidDocumentTypeError(Exception): pass


class DocumentoService:
    @staticmethod
    def create_from_form(form, user):
        """
        Cria um DocumentoContabilistico a partir do form, atribui o Client existente,
        valida tipo, guarda doc e associa notas.
        """
        # 1) Cliente existente
        client = form.client_existing.data
        if not client:
            raise DuplicateClientError("Selecione um cliente existente.")

        # 2) Valida tipo
        valid = [t.value for t in DocumentoContabilistico.tipo.type.enum_class]
        if form.tipo.data not in valid:
            raise InvalidDocumentTypeError("Tipo de documento inválido.")

        # 3) Monta e salva o documento
        doc = DocumentoContabilistico(
            user_id         = user.id,
            client_id       = client.id,
            numero          = form.numero.data,
            created_at      = form.data_emissao.data,
            advogado        = form.advogado.data,
            data_emissao    = form.data_emissao.data,
            details         = form.historico.data,
            valor           = Decimal(str(form.valor.data)),
            is_confirmed    = (form.status.data == 'paga'),
            tipo            = form.tipo.data,
            data_vencimento = form.data_vencimento.data,
            numero_cliente  = client.number_interno
        )
        DocumentoRepo.save(doc)

        # 4) Associa notas pendentes, se houver
        for nota in form.notas.data or []:
            nota.status = 'faturada'
            doc.notas.append(nota)
            BillingNotaRepo.save(nota)

        return doc
    
    @staticmethod
    def apply_filters_manage(query, params):
        """
        Aplica filtros vindos de request.args a um Query de DocumentoContabilistico.
        Primeiro filtra por numero_cliente, e se não houver numero_cliente,
        faz fallback para Client.name.
        """
        from sqlalchemy import or_, and_
        from app.clientes.models import Client
        from app.accounting.models import DocumentoContabilistico

        # 1) Filtrar por número de cliente, se fornecido
        if params.get('numero_cliente'):
            term = params['numero_cliente']
            query = query.filter(
                DocumentoContabilistico.numero_cliente.ilike(f"%{term}%")
            )

        # 2) Fallback para pesquisa por nome de cliente
        if params.get('cliente_nome'):
            term = params['cliente_nome']
            # junta a tabela Client para usar Client.name
            query = query.join(Client).filter(
                or_(
                    # documentos que tenham numero_cliente e combinem
                    DocumentoContabilistico.numero_cliente.ilike(f"%{term}%"),
                    # documentos sem numero_cliente cuja Client.name combine
                    and_(
                        or_(
                            DocumentoContabilistico.numero_cliente == None,
                            DocumentoContabilistico.numero_cliente == ''
                        ),
                        Client.name.ilike(f"%{term}%")
                    )
                )
            )

        # 3) Outros filtros padrão
        if params.get('tipo'):
            query = query.filter(DocumentoContabilistico.tipo == params['tipo'])
        if params.get('data_emissao'):
            query = query.filter(
                DocumentoContabilistico.data_emissao >= params['data_emissao']
            )
        if params.get('advogado'):
            query = query.filter(
                DocumentoContabilistico.advogado.ilike(f"%{params['advogado']}%")
            )
        if params.get('status'):
            st = params['status']
            if st == 'pendente':
                pend = ['pendente', 'tentativa_cobranca', 'em_tribunal', 'incobravel']
                query = query.filter(
                    DocumentoContabilistico.status_cobranca.in_(pend)
                )
            else:
                query = query.filter(
                    DocumentoContabilistico.status_cobranca == st
                )
        if params.get('dias_atraso'):
            try:
                d = int(params['dias_atraso'])
                query = query.filter(DocumentoContabilistico.dias_atraso <= d)
            except ValueError:
                pass

        return query

    @staticmethod
    def update_from_form(doc, form):
        # 1) desfaturar e dissociar antigas notas
        for old in list(doc.notas):
            old.status = 'pendente'
            doc.notas.remove(old)

        # 2) atualizar campos básicos (sem usar populate_obj para notas)
        doc.numero = form.numero.data
        doc.tipo = form.tipo.data
        doc.data_emissao = form.data_emissao.data
        doc.valor = form.valor.data
        doc.advogado = form.advogado.data
        doc.details = form.historico.data
        doc.data_vencimento = form.data_vencimento.data
        doc.is_confirmed = (form.status.data == 'paga')
        doc.status_cobranca = form.status.data

        # 3) faturar e associar novas notas
        for nota in form.notas.data or []:
            nota.status = 'faturada'
            doc.notas.append(nota)

        # 4) commit único para salvar documento, relações e status das notas
        db.session.commit()

        return doc

    @staticmethod
    def split_paid_pending(documents):
        """
        Recebe uma lista de DocumentoContabilistico e retorna duas listas:
        (paid_invoices, pending_invoices), com base em status_cobranca == 'paga'
        """
        paid    = [d for d in documents if d.status_cobranca == 'paga']
        pending = [d for d in documents if d.status_cobranca != 'paga']
        return paid, pending

    @staticmethod
    def apply_ordering(query, ordenar_por):
        field_map = {
            'data_emissao_asc':    DocumentoContabilistico.data_emissao.asc(),
            'data_emissao_desc':   DocumentoContabilistico.data_emissao.desc(),
            'data_vencimento_asc': DocumentoContabilistico.data_vencimento.asc(),
            'data_vencimento_desc':DocumentoContabilistico.data_vencimento.desc(),
            'valor_asc':           DocumentoContabilistico.valor.asc(),
            'valor_desc':          DocumentoContabilistico.valor.desc(),
        }
        return query.order_by(
            field_map.get(ordenar_por, DocumentoContabilistico.created_at.desc())
        )


class CsvService:
    @staticmethod
    def normalize_header(h):
        return unicodedata.normalize('NFKD', h.strip().lower())

    @staticmethod
    def parse_date(s):
        if not s:
            return None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def parse_csv(file_storage):
        raw = file_storage.stream.read()
        file_storage.stream.seek(0)

        # 1) Decodifica já a tentar BOM
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')  # fallback

        # 2) Detecção de dialect
        try:
            sample = text[:1024]
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel  # fallback para vírgula

        reader = csv.DictReader(StringIO(text), dialect=dialect)
        rows = []
        for row in reader:
            norm = {
                CsvService.normalize_header(k): (v.strip() if v else v)
                for k, v in row.items()
            }
            rows.append(norm)
        return rows


    @staticmethod
    def save_tmp(rows, user):
        tmp = TmpDocumento(data=rows, user_id=user.id)
        TmpDocumentoRepo.add(tmp)
        db.session.commit()
        return tmp

    @staticmethod
    def get_tmp(tmp_id, user):
        tmp = TmpDocumentoRepo.get(tmp_id)
        return tmp if tmp and tmp.user_id == user.id else None

    @staticmethod
    def import_tmp(tmp_id, user):
        tmp = CsvService.get_tmp(tmp_id, user)
        if not tmp:
            raise ValueError("CSV não encontrado ou não autorizado")
        docs = []
        for row in tmp.data:
            cname = (row.get('client') or row.get('cliente') or '').strip()
            num = row.get('numero_cliente')
            client = ClienteRepo.find_by_user_and_name(user.id, cname)
            if not client:
                client = Client(user_id=user.id, name=cname, number_interno=num)
                ClienteRepo.add(client)
            else:
                if num and not client.number_interno:
                    client.number_interno = num

            dv = CsvService.parse_date(row.get('data_emissao'))
            doc = DocumentoContabilistico(
                user_id=user.id,
                client_id=client.id,
                numero=row.get('numero'),
                created_at=dv,
                data_emissao=dv,
                data_vencimento=CsvService.parse_date(row.get('data_vencimento')),
                tipo=row.get('tipo', 'fatura'),
                valor=Decimal(row.get('valor') or '0'),
                advogado=row.get('advogado'),
                details=row.get('historico'),
                status_cobranca=row.get('status', 'pendente'),
                numero_recibo=row.get('numero_recibo'),
                numero_cliente=num,
                is_confirmed=(row.get('status') == 'paga')
            )
            docs.append(doc)

        with db.session.begin():
            db.session.bulk_save_objects(docs)
            TmpDocumentoRepo.delete(tmp)

        return len(docs)
