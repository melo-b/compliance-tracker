"""Add role to users

Existing accounts become READ_ONLY. Promote the first administrator with
`python -m app.scripts.create_admin`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = sa.Enum("ADMIN", "ENGINEER", "READ_ONLY", name="userrole")


def upgrade() -> None:
    # PostgreSQL needs the enum type to exist before a column can use it
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("role", user_role, nullable=False, server_default="READ_ONLY"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS userrole")
