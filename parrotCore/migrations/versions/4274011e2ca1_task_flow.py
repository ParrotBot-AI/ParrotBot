"""task_flow

Revision ID: 4274011e2ca1
Revises: 4c3e080eaa65
Create Date: 2024-02-23 22:27:20.678844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '4274011e2ca1'
down_revision: Union[str, None] = '4c3e080eaa65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('TaskFlows', sa.Column('result', sa.Text(), nullable=True))
    op.drop_constraint('TaskFlowsConditions_ibfk_1', 'TaskFlowsConditions', type_='foreignkey')
    op.drop_column('TaskFlowsConditions', 'current_module_id')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('TaskFlowsConditions', sa.Column('current_module_id', mysql.INTEGER(), autoincrement=False, nullable=False))
    op.create_foreign_key('TaskFlowsConditions_ibfk_1', 'TaskFlowsConditions', 'Modules', ['current_module_id'], ['id'], ondelete='CASCADE')
    op.drop_column('TaskFlows', 'result')
    # ### end Alembic commands ###