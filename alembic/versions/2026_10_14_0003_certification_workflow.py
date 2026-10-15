"""Certification workflow: workflow_status, certificate details, computed validity

Replaces the stored `status` column (Pending / Valid / Expiring Soon / Expired) with:
  * workflow_status  Pending -> Draft -> Final, set by people
  * certificate_number, issued_date, agency  (optional certificate details)
Validity (Valid / Expiring Soon / Expired) is no longer stored; it is computed from
expiration_date when a record is read.

Data conversion: Pending stays PENDING. Valid / Expiring Soon / Expired all meant "a certificate
was issued", so they become FINAL; whether such a record is currently valid is now derived from
its expiration_date. A record that was marked Expired by hand but has no expiration_date will
therefore read as "Valid - No expiry" afterwards and needs its expiration_date entered.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

workflow_status = sa.Enum("PENDING", "DRAFT", "FINAL", name="workflowstatus")
old_status = sa.Enum("PENDING", "VALID", "EXPIRING_SOON", "EXPIRED", name="compliancestatus")


def upgrade() -> None:
    bind = op.get_bind()
    workflow_status.create(bind, checkfirst=True)

    with op.batch_alter_table("product_compliance") as batch:
        batch.add_column(
            sa.Column("workflow_status", workflow_status, nullable=False, server_default="PENDING")
        )
        batch.add_column(sa.Column("certificate_number", sa.String(), nullable=True))
        batch.add_column(sa.Column("issued_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("agency", sa.String(), nullable=True))

    # Anything that was not Pending had been issued
    op.execute("UPDATE product_compliance SET workflow_status = 'FINAL' WHERE status <> 'PENDING'")

    with op.batch_alter_table("product_compliance") as batch:
        batch.drop_column("status")

    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS compliancestatus")


def downgrade() -> None:
    bind = op.get_bind()
    old_status.create(bind, checkfirst=True)

    with op.batch_alter_table("product_compliance") as batch:
        batch.add_column(
            sa.Column("status", old_status, nullable=False, server_default="PENDING")
        )

    # Rebuild the stored status from the computed one. The old "Expiring Soon" state was a
    # worker-maintained flag, so it is not reconstructed here: such records come back as Valid.
    # (Separate statements with plain literals: PostgreSQL will not assign a CASE expression to
    # an enum column without a cast, and a cast type name is not portable to SQLite.)
    op.execute("UPDATE product_compliance SET status = 'PENDING' WHERE workflow_status <> 'FINAL'")
    op.execute(
        "UPDATE product_compliance SET status = 'EXPIRED' "
        "WHERE workflow_status = 'FINAL' AND expiration_date < CURRENT_DATE"
    )
    op.execute(
        "UPDATE product_compliance SET status = 'VALID' "
        "WHERE workflow_status = 'FINAL' "
        "AND (expiration_date IS NULL OR expiration_date >= CURRENT_DATE)"
    )

    with op.batch_alter_table("product_compliance") as batch:
        batch.drop_column("workflow_status")
        batch.drop_column("certificate_number")
        batch.drop_column("issued_date")
        batch.drop_column("agency")

    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS workflowstatus")
