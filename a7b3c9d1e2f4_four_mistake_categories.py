"""four mistake categories: misconception, careless slip, gap in understanding, calculation error

Revision ID: a7b3c9d1e2f4
Revises: f63a9b4d2e58
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b3c9d1e2f4"
down_revision: Union[str, Sequence[str], None] = "f63a9b4d2e58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALLOWED = "('MISCONCEPTION', 'CARELESS_SLIP', 'GAP_IN_UNDERSTANDING', 'CALCULATION_ERROR')"
# JSON columns whose stored text carries the old names
RENAMES = [
    ('"verdict": "slip"', '"verdict": "careless_slip"'),
    ('"verdict": "unknown"', '"verdict": "gap_in_understanding"'),
    ('INCOMPLETE_UNDERSTANDING', 'GAP_IN_UNDERSTANDING'),
    ('Incomplete Understanding', 'Gap in Understanding'),
    ('Incomplete understanding', 'Gap in understanding'),
    ('MISINTERPRETATION', 'CARELESS_SLIP'),
]


def _replace_json(table: str, column: str, a: str, b: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(f"UPDATE {table} SET {column} = CAST(REPLACE(CAST({column} AS TEXT), :a, :b) AS JSON) WHERE CAST({column} AS TEXT) LIKE :like").bindparams(a=a, b=b, like=f"%{a}%"))
    else:
        op.execute(sa.text(f"UPDATE {table} SET {column} = REPLACE({column}, :a, :b) WHERE {column} LIKE :like").bindparams(a=a, b=b, like=f"%{a}%"))


def upgrade() -> None:
    # stored diagnoses: a misreading is a careless slip; an incomplete understanding is a gap in understanding
    op.execute("UPDATE diagnostic_sessions SET final_diagnosis = 'GAP_IN_UNDERSTANDING' WHERE final_diagnosis = 'INCOMPLETE_UNDERSTANDING'")
    op.execute("UPDATE diagnostic_sessions SET final_diagnosis = 'CARELESS_SLIP' WHERE final_diagnosis = 'MISINTERPRETATION'")
    op.execute("UPDATE diagnostic_sessions SET primary_hypothesis = 'GAP_IN_UNDERSTANDING' WHERE primary_hypothesis = 'INCOMPLETE_UNDERSTANDING'")
    op.execute("UPDATE diagnostic_sessions SET primary_hypothesis = 'CARELESS_SLIP' WHERE primary_hypothesis = 'MISINTERPRETATION'")
    op.execute("UPDATE mistake_logs SET mistake_type = 'GAP_IN_UNDERSTANDING' WHERE mistake_type = 'INCOMPLETE_UNDERSTANDING'")
    for column in ("final", "initial", "alternative_hypotheses"):
        for a, b in RENAMES:
            _replace_json("diagnostic_sessions", column, a, b)
    for a, b in RENAMES[2:]:
        _replace_json("attempts", "evaluation", a, b)
    # only the four categories can be stored from now on
    with op.batch_alter_table("diagnostic_sessions") as batch:
        batch.create_check_constraint("ck_diagnosis_category", f"final_diagnosis IS NULL OR final_diagnosis IN {ALLOWED}")
    with op.batch_alter_table("mistake_logs") as batch:
        batch.create_check_constraint("ck_mistake_category", f"mistake_type IN {ALLOWED}")


def downgrade() -> None:
    with op.batch_alter_table("mistake_logs") as batch:
        batch.drop_constraint("ck_mistake_category", type_="check")
    with op.batch_alter_table("diagnostic_sessions") as batch:
        batch.drop_constraint("ck_diagnosis_category", type_="check")
    op.execute("UPDATE diagnostic_sessions SET final_diagnosis = 'INCOMPLETE_UNDERSTANDING' WHERE final_diagnosis = 'GAP_IN_UNDERSTANDING'")
    op.execute("UPDATE mistake_logs SET mistake_type = 'INCOMPLETE_UNDERSTANDING' WHERE mistake_type = 'GAP_IN_UNDERSTANDING'")
