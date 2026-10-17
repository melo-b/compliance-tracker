"""Baseline schema

Captures the schema that was previously created by Base.metadata.create_all().

Each table is created only if it does not already exist, so this migration is safe to run
both on a brand-new database and on an existing one that was built by create_all() (such as
the live demo database). Later migrations are ordinary, non-idempotent migrations.

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_id", "users", ["id"], unique=False)
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "products" not in existing:
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("model_number", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_products_id", "products", ["id"], unique=False)
        op.create_index("ix_products_model_number", "products", ["model_number"], unique=True)

    if "standards" not in existing:
        op.create_table(
            "standards",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("standard_number", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("publication_date", sa.Date(), nullable=True),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("issuing_body", sa.String(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("ACTIVE", "PENDING", "RETIRED", name="standardstatus"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_standards_id", "standards", ["id"], unique=False)
        op.create_index(
            "ix_standards_standard_number", "standards", ["standard_number"], unique=True
        )

    if "product_compliance" not in existing:
        op.create_table(
            "product_compliance",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("standard_id", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("PENDING", "VALID", "EXPIRING_SOON", "EXPIRED", name="compliancestatus"),
                nullable=False,
            ),
            sa.Column("expiration_date", sa.Date(), nullable=True),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.ForeignKeyConstraint(["standard_id"], ["standards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_product_compliance_id", "product_compliance", ["id"], unique=False)

    if "documents" not in existing:
        op.create_table(
            "documents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("upload_date", sa.DateTime(), nullable=True),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("standard_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.ForeignKeyConstraint(["standard_id"], ["standards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_documents_id", "documents", ["id"], unique=False)


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("product_compliance")
    op.drop_table("standards")
    op.drop_table("products")
    op.drop_table("users")
    # PostgreSQL keeps enum types after the tables that use them are dropped
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS standardstatus")
        op.execute("DROP TYPE IF EXISTS compliancestatus")
