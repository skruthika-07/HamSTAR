"""photos sent with answers

Revision ID: f63a9b4d2e58
Revises: e52f8a3c1d47
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f63a9b4d2e58"
down_revision: Union[str, Sequence[str], None] = "e52f8a3c1d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "answer_images" in sa.inspect(op.get_bind()).get_table_names():
        return  # the app also creates missing tables on start
    op.create_table(
        "answer_images",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_id", sa.String(length=32), sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("file_path", sa.String(length=400), nullable=False),
        sa.Column("file_name", sa.String(length=200), nullable=False),
        sa.Column("mime", sa.String(length=40), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for col in ("user_id", "attempt_id", "created_at"):
        op.create_index(f"ix_answer_images_{col}", "answer_images", [col])


def downgrade() -> None:
    op.drop_table("answer_images")
