"""indicators

Revision ID: 8b0c8b3f6ebf
Revises: f72cc02b0f49
Create Date: 2024-03-21 01:33:11.384325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '8b0c8b3f6ebf'
down_revision: Union[str, None] = 'f72cc02b0f49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Submissions', 'score',
               existing_type=mysql.INTEGER(),
               type_=sa.Float(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Submissions', 'score',
               existing_type=sa.Float(),
               type_=mysql.INTEGER(),
               existing_nullable=True)
    # ### end Alembic commands ###