"""profile life events questionnaire

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01 00:07:24.737592
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "life_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_life_events_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_life_events")),
    )
    op.create_index("ix_life_events_user_source", "life_events", ["user_id", "source"], unique=False)
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("resident", sa.Boolean(), nullable=True),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("marital_status", sa.String(length=16), nullable=True),
        sa.Column("single_parent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("disability", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_profiles")),
    )
    op.create_table(
        "questionnaire_answers",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_questionnaire_answers_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "question_id", name=op.f("pk_questionnaire_answers")),
    )


def downgrade() -> None:
    op.drop_table("questionnaire_answers")
    op.drop_table("profiles")
    op.drop_index("ix_life_events_user_source", table_name="life_events")
    op.drop_table("life_events")
