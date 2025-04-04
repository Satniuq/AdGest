"""Atualiza campo nickname para ser obrigatório e adiciona email com valores únicos

Revision ID: 0c1c06273bf5
Revises: da16a8fffe20
Create Date: 2025-03-31 17:27:05.329074

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0c1c06273bf5'
down_revision = 'da16a8fffe20'
branch_labels = None
depends_on = None


def upgrade():
    # Remova a tabela temporária, se existir
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_users")
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nickname', sa.String(length=10), nullable=False, server_default='UNK'))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('profile_image', sa.String(length=120), nullable=True))
        batch_op.create_unique_constraint('uq_users_email', ['email'])
    
    # Preenche os registros existentes com um email único, se necessário
    op.execute("UPDATE users SET email = 'user_' || id || '@example.com' WHERE email IS NULL")
    
    # Remova novamente a tabela temporária, se existir, antes de alterar a coluna
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_users")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('email', nullable=False)
    
    # Remova o default temporário de 'nickname'
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_users")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('nickname', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_email', type_='unique')
        batch_op.drop_column('profile_image')
        batch_op.drop_column('email')
        batch_op.drop_column('nickname')
