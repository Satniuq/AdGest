"""Recreate shared_tarefas with cascade on delete

Revision ID: <novo_revision_id>
Revises: <ID_da_migração_anterior>
Create Date: 2025-04-02 HH:MM:SS
"""

# Revisão e importações padrão
revision = '<novo_revision_id>'
down_revision = '<ID_da_migração_anterior>'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Descartar a tabela antiga (caso exista dados críticos, faça backup)
    op.drop_table('shared_tarefas')
    # Recriar a tabela com os nomes de constraint e ondelete="CASCADE"
    op.create_table(
        'shared_tarefas',
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete="CASCADE", name='fk_shared_tarefas_user_id'), primary_key=True),
        sa.Column('tarefa_id', sa.Integer, sa.ForeignKey('tarefas.id', ondelete="CASCADE", name='fk_shared_tarefas_tarefa_id'), primary_key=True)
    )

def downgrade():
    op.drop_table('shared_tarefas')
    # Caso queira recriar a tabela com a definição antiga, adapte conforme seu modelo original:
    op.create_table(
        'shared_tarefas',
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('tarefa_id', sa.Integer, sa.ForeignKey('tarefas.id'))
    )
