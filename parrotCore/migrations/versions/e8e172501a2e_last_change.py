"""last change

Revision ID: e8e172501a2e
Revises: 65b787ae4e45
Create Date: 2024-03-31 22:35:35.287747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'e8e172501a2e'
down_revision: Union[str, None] = '65b787ae4e45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Accounts', sa.Column('estimate_score', sa.Float(), nullable=True))
    op.drop_column('Accounts', 'est_score')
    op.alter_column('Indicators', 'father_indicator',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.add_column('TaskAccounts', sa.Column('status', sa.Integer(), nullable=True))
    op.add_column('TaskAccounts', sa.Column('due_time', sa.DateTime(), nullable=True))
    op.add_column('TaskAccounts', sa.Column('level', sa.Integer(), nullable=True))
    op.add_column('Users', sa.Column('plan_due_time', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('Users', 'plan_due_time')
    op.drop_column('TaskAccounts', 'level')
    op.drop_column('TaskAccounts', 'due_time')
    op.drop_column('TaskAccounts', 'status')
    op.alter_column('Indicators', 'father_indicator',
               existing_type=mysql.INTEGER(),
               nullable=True)
    op.add_column('Accounts', sa.Column('est_score', mysql.FLOAT(), nullable=True))
    op.drop_column('Accounts', 'estimate_score')
    # ### end Alembic commands ###
