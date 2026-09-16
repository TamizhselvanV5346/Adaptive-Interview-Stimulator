"""create_candidate_responses_table

Revision ID: e2b4c6a8f101
Revises: bf19f09bc1bf
Create Date: 2026-09-16 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b4c6a8f101'
down_revision: Union[str, Sequence[str], None] = 'bf19f09bc1bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'candidate_responses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('interview_session_id', sa.Uuid(), nullable=False),
        sa.Column('question_id', sa.Uuid(), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('candidate_answer', sa.Text(), nullable=False),
        sa.Column('evaluation_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('turn_number >= 0', name='chk_candidate_response_turn_number_non_negative'),
        sa.ForeignKeyConstraint(['interview_session_id'], ['interview_sessions.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidate_responses_interview_session_id'), 'candidate_responses', ['interview_session_id'], unique=False)
    op.create_index(op.f('ix_candidate_responses_organization_id'), 'candidate_responses', ['organization_id'], unique=False)
    op.create_index(op.f('ix_candidate_responses_question_id'), 'candidate_responses', ['question_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_candidate_responses_question_id'), table_name='candidate_responses')
    op.drop_index(op.f('ix_candidate_responses_organization_id'), table_name='candidate_responses')
    op.drop_index(op.f('ix_candidate_responses_interview_session_id'), table_name='candidate_responses')
    op.drop_table('candidate_responses')
