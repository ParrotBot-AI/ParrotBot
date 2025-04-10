"""submission revision

Revision ID: 0e1553032b45
Revises: 12fbcfc50d8a
Create Date: 2024-01-30 14:05:35.290388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '0e1553032b45'
down_revision: Union[str, None] = '12fbcfc50d8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Submissions', 'cal_method',
               existing_type=mysql.INTEGER(),
               type_=sa.Text(),
               existing_nullable=True)
    op.alter_column('Submissions', 'is_graded',
               existing_type=mysql.INTEGER(),
               type_=sa.Boolean(),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Submissions', 'is_graded',
               existing_type=sa.Boolean(),
               type_=mysql.INTEGER(),
               existing_nullable=False)
    op.alter_column('Submissions', 'cal_method',
               existing_type=sa.Text(),
               type_=mysql.INTEGER(),
               existing_nullable=True)
    # ### end Alembic commands ###
