"""update mod action indices

Revision ID: 365caa1cbd80
Revises: 3cb15662f688
Create Date: 2020-02-28 21:56:48.045412

"""

# revision identifiers, used by Alembic.
revision = '365caa1cbd80'
down_revision = '3cb15662f688'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_development():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_mod_actions_action'), 'mod_actions', ['action'], unique=False)
    op.create_index(op.f('ix_mod_actions_created_utc'), 'mod_actions', ['created_utc'], unique=False)
    op.create_index(op.f('ix_mod_actions_mod'), 'mod_actions', ['mod'], unique=False)
    # ### end Alembic commands ###


def downgrade_development():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_mod_actions_mod'), table_name='mod_actions')
    op.drop_index(op.f('ix_mod_actions_created_utc'), table_name='mod_actions')
    op.drop_index(op.f('ix_mod_actions_action'), table_name='mod_actions')
    # ### end Alembic commands ###


def upgrade_test():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_mod_actions_action'), 'mod_actions', ['action'], unique=False)
    op.create_index(op.f('ix_mod_actions_created_utc'), 'mod_actions', ['created_utc'], unique=False)
    op.create_index(op.f('ix_mod_actions_mod'), 'mod_actions', ['mod'], unique=False)
    # ### end Alembic commands ###


def downgrade_test():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_mod_actions_mod'), table_name='mod_actions')
    op.drop_index(op.f('ix_mod_actions_created_utc'), table_name='mod_actions')
    op.drop_index(op.f('ix_mod_actions_action'), table_name='mod_actions')
    # ### end Alembic commands ###


def upgrade_production():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_mod_actions_action'), 'mod_actions', ['action'], unique=False)
    op.create_index(op.f('ix_mod_actions_created_utc'), 'mod_actions', ['created_utc'], unique=False)
    op.create_index(op.f('ix_mod_actions_mod'), 'mod_actions', ['mod'], unique=False)
    # ### end Alembic commands ###


def downgrade_production():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_mod_actions_mod'), table_name='mod_actions')
    op.drop_index(op.f('ix_mod_actions_created_utc'), table_name='mod_actions')
    op.drop_index(op.f('ix_mod_actions_action'), table_name='mod_actions')
    # ### end Alembic commands ###

