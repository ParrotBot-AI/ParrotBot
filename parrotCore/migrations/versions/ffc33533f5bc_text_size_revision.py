"""text size revision

Revision ID: ffc33533f5bc
Revises: 83a2dceaa03d
Create Date: 2024-01-29 12:32:51.136213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'ffc33533f5bc'
down_revision: Union[str, None] = '83a2dceaa03d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Questions', 'keywords',
               existing_type=mysql.VARCHAR(length=100),
               type_=sa.Text(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Questions', 'keywords',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=100),
               existing_nullable=True)
    # ### end Alembic commands ###