"""word constrains

Revision ID: f3849832e7d9
Revises: 3c68406fb55e
Create Date: 2024-02-23 09:20:27.492856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f3849832e7d9'
down_revision: Union[str, None] = '3c68406fb55e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Vocabs', 'word',
               existing_type=mysql.TEXT(),
               type_=sa.String(length=50),
               existing_nullable=False)
    op.create_unique_constraint(None, 'Vocabs', ['word'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'Vocabs', type_='unique')
    op.alter_column('Vocabs', 'word',
               existing_type=sa.String(length=50),
               type_=mysql.TEXT(),
               existing_nullable=False)
    # ### end Alembic commands ###