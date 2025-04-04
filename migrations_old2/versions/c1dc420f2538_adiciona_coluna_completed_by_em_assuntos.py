"""Adiciona coluna completed_by em assuntos, prazos_judiciais e tarefas

Revision ID: c1dc420f2538
Revises: 5ea01f2b3a85
Create Date: 2025-03-25 00:50:35.955601

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1dc420f2538'
down_revision = '5ea01f2b3a85'
branch_labels = None
depends_on = None


def upgrade():
    # Se a tabela "horas_adicao" já existe, comente ou remova a criação
    # op.create_table(
    #     'horas_adicao',
    #     sa.Column('id', sa.Integer(), nullable=False),
    #     sa.Column('item_type', sa.String(length=20), nullable=False),
    #     sa.Column('item_id', sa.Integer(), nullable=False),
    #     sa.Column('horas_adicionadas', sa.Float(), nullable=False),
    #     sa.Column('user_id', sa.Integer(), nullable=False),
    #     sa.Column('timestamp', sa.DateTime(), nullable=True),
    #     sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_horas_adicao_user_id'),
    #     sa.PrimaryKeyConstraint('id')
    # )

    # Alterar a tabela "assuntos": adicionar a coluna "completed_by" com constraint nomeada
    with op.batch_alter_table('assuntos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completed_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_assuntos_completed_by',  # nome da constraint
            'users',                     # tabela referenciada
            ['completed_by'],            # coluna local
            ['id']                       # coluna referenciada
        )

    # Alterar a tabela "prazos_judiciais"
    with op.batch_alter_table('prazos_judiciais', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completed_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_prazos_completed_by',
            'users',
            ['completed_by'],
            ['id']
        )

    # Alterar a tabela "tarefas"
    with op.batch_alter_table('tarefas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completed_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_tarefas_completed_by',
            'users',
            ['completed_by'],
            ['id']
        )

    # Alterar a tabela "client_shares" para deixar o campo "option" como NOT NULL
    with op.batch_alter_table('client_shares', schema=None) as batch_op:
        batch_op.alter_column('option',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)


def downgrade():
    with op.batch_alter_table('tarefas', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tarefas_completed_by', type_='foreignkey')
        batch_op.drop_column('completed_by')

    with op.batch_alter_table('prazos_judiciais', schema=None) as batch_op:
        batch_op.drop_constraint('fk_prazos_completed_by', type_='foreignkey')
        batch_op.drop_column('completed_by')

    with op.batch_alter_table('client_shares', schema=None) as batch_op:
        batch_op.alter_column('option',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)

    with op.batch_alter_table('assuntos', schema=None) as batch_op:
        batch_op.drop_constraint('fk_assuntos_completed_by', type_='foreignkey')
        batch_op.drop_column('completed_by')

    # op.drop_table('horas_adicao')
