"""submission revision pause time

Revision ID: a8a4bf86e519
Revises: 0e1553032b45
Create Date: 2024-01-30 15:23:20.312402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8a4bf86e519'
down_revision: Union[str, None] = '0e1553032b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('AnswerSheetRecord', sa.Column('last_pause_time', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('AnswerSheetRecord', 'last_pause_time')
    # ### end Alembic commands ###