"""error

Revision ID: f9873884b103
Revises: 2f51d2a97ae6
Create Date: 2024-03-24 16:17:29.590133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9873884b103'
down_revision: Union[str, None] = '2f51d2a97ae6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Questions', sa.Column('error_feedback', sa.Text(), nullable=True))
    op.add_column('VocabsLearning', sa.Column('is_skip_remind', sa.Integer(), nullable=True))
    op.add_column('VocabsLearning', sa.Column('refuse_skip', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('VocabsLearning', 'refuse_skip')
    op.drop_column('VocabsLearning', 'is_skip_remind')
    op.drop_column('Questions', 'error_feedback')
    # ### end Alembic commands ###
