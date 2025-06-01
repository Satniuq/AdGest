# app/billing/services.py

from sqlalchemy import and_
from app import db
from app.billing.models import BillingNota

class BillingService:

    @staticmethod
    def search_notas(source_type=None, date_from=None, date_to=None, created_by=None):
        q = BillingNota.query
        if source_type:
            q = q.filter(BillingNota.source_type == source_type)
        if date_from:
            q = q.filter(BillingNota.created_at >= date_from)
        if date_to:
            q = q.filter(BillingNota.created_at <= date_to)
        if created_by:
            q = q.filter(BillingNota.created_by == created_by)
        return q.order_by(BillingNota.created_at.desc()).all()


    @staticmethod
    def get_nota(nota_id):
        return BillingNota.query.get_or_404(nota_id)
