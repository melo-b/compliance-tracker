"""Migration 0004: unique product/standard mapping, indexes and document metadata."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'm4.db').as_posix()}"


@pytest.fixture
def alembic_cfg(db_url):
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def seed(connection, mappings):
    connection.execute(sa.text("INSERT INTO products (name, model_number) VALUES ('P', 'M1')"))
    for number in {standard for _, standard in mappings}:
        connection.execute(
            sa.text(
                "INSERT INTO standards (standard_number, title, issuing_body, status) "
                "VALUES (:n, 'T', 'CSA', 'ACTIVE')"
            ),
            {"n": f"S{number}"},
        )
    for product, standard in mappings:
        connection.execute(
            sa.text(
                "INSERT INTO product_compliance (product_id, standard_id, workflow_status) "
                "VALUES (:p, :s, 'PENDING')"
            ),
            {"p": product, "s": standard},
        )


def test_existing_records_survive_and_new_columns_are_empty(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "0003")
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        seed(connection, [(1, 1), (1, 2)])
        connection.execute(
            sa.text(
                "INSERT INTO documents (filename, file_path, product_id) "
                "VALUES ('a.pdf', 'uploads/x', 1)"
            )
        )

    command.upgrade(alembic_cfg, "head")

    with engine.connect() as connection:
        mappings = connection.execute(
            sa.text("SELECT COUNT(*) FROM product_compliance")
        ).scalar_one()
        document = connection.execute(
            sa.text("SELECT filename, content_type, size_bytes FROM documents")
        ).one()
    engine.dispose()
    assert mappings == 2
    assert tuple(document) == ("a.pdf", None, None)  # old documents simply lack the new metadata


def test_the_database_enforces_one_mapping_per_product_and_standard(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        seed(connection, [(1, 1)])

    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO product_compliance (product_id, standard_id, workflow_status) "
                    "VALUES (1, 1, 'DRAFT')"
                )
            )
    engine.dispose()


def test_the_migration_refuses_to_run_over_duplicates_and_changes_nothing(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "0003")
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        seed(connection, [(1, 1), (1, 1)])  # a duplicate that predates the constraint

    with pytest.raises(RuntimeError) as error:
        command.upgrade(alembic_cfg, "head")

    assert "(product 1, standard 1) x2" in str(error.value)
    assert "Delete the extra records" in str(error.value)
    with engine.connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        rows = connection.execute(sa.text("SELECT COUNT(*) FROM product_compliance")).scalar_one()
    engine.dispose()
    assert version == "0003"  # still at the previous revision
    assert rows == 2  # and nothing was deleted on anyone's behalf


def test_downgrade_removes_the_constraint_indexes_and_columns(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0003")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)
    document_columns = {c["name"] for c in inspector.get_columns("documents")}
    compliance_indexes = {i["name"] for i in inspector.get_indexes("product_compliance")}
    unique_constraints = {u["name"] for u in inspector.get_unique_constraints("product_compliance")}
    engine.dispose()

    assert {"content_type", "size_bytes"}.isdisjoint(document_columns)
    assert "ix_product_compliance_workflow_expiry" not in compliance_indexes
    assert "uq_product_compliance_product_standard" not in unique_constraints


def test_the_models_match_the_migrated_schema(alembic_cfg):
    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)
