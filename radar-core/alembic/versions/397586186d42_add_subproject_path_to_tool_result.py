"""add subproject_path to tool_result

Revision ID: 397586186d42
Revises: 555ffc592f67
Create Date: 2026-08-28 00:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "397586186d42"
down_revision = "555ffc592f67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tool_result", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("subproject_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False)
        )
        batch_op.create_index(
            batch_op.f("ix_tool_result_subproject_path"), ["subproject_path"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("tool_result", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tool_result_subproject_path"))
        batch_op.drop_column("subproject_path")
