"""tasks with deadlines and reminders

Revision ID: e52f8a3c1d47
Revises: c41d7e2a9b10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e52f8a3c1d47"
down_revision: Union[str, Sequence[str], None] = "c41d7e2a9b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # the app also creates missing tables on start
    if "tasks" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("starred", sa.Boolean(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for col in ("user_id", "done", "deadline", "created_at"):
        op.create_index(f"ix_tasks_{col}", "tasks", [col])


def downgrade() -> None:
    op.drop_table("tasks")
