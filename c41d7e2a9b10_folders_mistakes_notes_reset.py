"""parent folders, mistake log, notes, password reset codes

Revision ID: c41d7e2a9b10
Revises: a97112134a27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c41d7e2a9b10"
down_revision: Union[str, Sequence[str], None] = "a97112134a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # the app also creates missing tables on start, so each step first checks what is already there
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "parent_subject" not in {c["name"] for c in insp.get_columns("study_materials")}:
        with op.batch_alter_table("study_materials", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_subject", sa.String(length=80), nullable=True))
    if "password_resets" not in tables:
        op.create_table(
            "password_resets",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code_hash", sa.String(length=100), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
        op.create_index("ix_password_resets_created_at", "password_resets", ["created_at"])
    if "mistake_logs" not in tables:
        op.create_table(
            "mistake_logs",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("attempt_id", sa.String(length=32), sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("question_id", sa.String(length=40), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("concept", sa.String(length=120), nullable=False),
            sa.Column("concept_key", sa.String(length=120), nullable=False),
            sa.Column("document", sa.String(length=60), nullable=False),
            sa.Column("folder", sa.String(length=80), nullable=False),
            sa.Column("parent", sa.String(length=80), nullable=False),
            sa.Column("mistake_type", sa.String(length=30), nullable=False),
            sa.Column("fixes", sa.Integer(), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        for col in ("user_id", "question_id", "concept_key", "document", "mistake_type", "resolved", "created_at"):
            op.create_index(f"ix_mistake_logs_{col}", "mistake_logs", [col])
    if "notes" not in tables:
        op.create_table(
            "notes",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("file_name", sa.String(length=200), nullable=False),
            sa.Column("content", sa.JSON(), nullable=False),
            sa.Column("markdown", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_notes_user_id", "notes", ["user_id"])
        op.create_index("ix_notes_created_at", "notes", ["created_at"])


def downgrade() -> None:
    for table in ("notes", "mistake_logs", "password_resets"):
        op.drop_table(table)
    with op.batch_alter_table("study_materials", schema=None) as batch_op:
        batch_op.drop_column("parent_subject")
