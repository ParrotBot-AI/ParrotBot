"""model used

Revision ID: 7e76051559e2
Revises: 88737f97c299
Create Date: 2024-03-11 17:06:17.606307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e76051559e2'
down_revision: Union[str, None] = '88737f97c299'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Accounts', sa.Column('model_today_used', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('Accounts', 'model_today_used')
    # ### end Alembic commands ###