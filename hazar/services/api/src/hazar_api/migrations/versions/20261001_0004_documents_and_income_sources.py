"""documents and income sources

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01 00:35:37.779621
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=True),
        sa.Column("object_key", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("extractor", sa.String(length=32), nullable=True),
        sa.Column("extraction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confirmed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_documents_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index("ix_documents_user_created", "documents", ["user_id", "created_at"], unique=False)
    op.create_table(
        "income_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("employer_name", sa.String(length=120), nullable=True),
        sa.Column("employer_file_number", sa.String(length=20), nullable=True),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_income_sources_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_income_sources_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_sources")),
        sa.UniqueConstraint("document_id", name=op.f("uq_income_sources_document_id")),
    )
    op.create_index(op.f("ix_income_sources_user_id"), "income_sources", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_income_sources_user_id"), table_name="income_sources")
    op.drop_table("income_sources")
    op.drop_index("ix_documents_user_created", table_name="documents")
    op.drop_table("documents")
