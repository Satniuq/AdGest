"""Descrição da mudança

Revision ID: ed57b610a7e7
Revises: 855ba48a68e8
Create Date: 2025-03-29 00:50:43.989221

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed57b610a7e7'
down_revision = '855ba48a68e8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('documentos_contabilisticos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('numero_recibo', sa.String(length=50), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('documentos_contabilisticos', schema=None) as batch_op:
        batch_op.drop_column('numero_recibo')

    # ### end Alembic commands ###
