"""Unique product/standard mapping, query indexes, document metadata

* product_compliance: unique (product_id, standard_id), enforced by the database so concurrent
  requests cannot create duplicate mappings; plus indexes for the dashboard and the
  validity / expiry filters
* documents: content_type and size_bytes (shown in the UI and used for downloads) and an
  index on product_id

The unique constraint cannot be added if duplicate mappings already exist. The API has always
rejected duplicates, so there should be none; if there are, this migration stops with the list
instead of deleting anything, so a person can decide which record to keep.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIQUE_NAME = "uq_product_compliance_product_standard"


def _refuse_duplicate_mappings(connection) -> None:
    duplicates = connection.execute(
        sa.text(
            "SELECT product_id, standard_id, COUNT(*) AS copies "
            "FROM product_compliance GROUP BY product_id, standard_id HAVING COUNT(*) > 1"
        )
    ).all()
    if duplicates:
        listing = ", ".join(f"(product {p}, standard {s}) x{n}" for p, s, n in duplicates)
        raise RuntimeError(
            "Cannot add the unique product/standard constraint because duplicate mappings "
            f"exist: {listing}. Delete the extra records and run the migration again."
        )


def upgrade() -> None:
    _refuse_duplicate_mappings(op.get_bind())

    with op.batch_alter_table("product_compliance") as batch:
        batch.create_unique_constraint(UNIQUE_NAME, ["product_id", "standard_id"])
        batch.create_index("ix_product_compliance_standard_id", ["standard_id"])
        batch.create_index(
            "ix_product_compliance_workflow_expiry", ["workflow_status", "expiration_date"]
        )

    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("content_type", sa.String(), nullable=True))
        batch.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch.create_index("ix_documents_product_id", ["product_id"])


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_index("ix_documents_product_id")
        batch.drop_column("size_bytes")
        batch.drop_column("content_type")

    with op.batch_alter_table("product_compliance") as batch:
        batch.drop_index("ix_product_compliance_workflow_expiry")
        batch.drop_index("ix_product_compliance_standard_id")
        batch.drop_constraint(UNIQUE_NAME, type_="unique")
