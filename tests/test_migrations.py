import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

import app.models  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TABLES = {
    "users",
    "products",
    "standards",
    "product_compliance",
    "documents",
}


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"


@pytest.fixture
def alembic_cfg(db_url):
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def table_names(url):
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_builds_the_full_schema_from_an_empty_database(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "head")
    assert EXPECTED_TABLES <= table_names(db_url)


def test_migrations_match_the_models(alembic_cfg):
    """Fails when a model changes without a matching migration (schema drift)."""
    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)


def test_upgrade_adopts_a_database_that_alembic_has_never_managed(alembic_cfg, db_url):
    """The live demo database was built by create_all() before Alembic existed.

    That is the baseline schema with no alembic_version table. Upgrading it must keep the
    existing tables and data, and apply only what is missing.
    """
    command.upgrade(alembic_cfg, "0001")
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users (email, hashed_password, is_active) "
                "VALUES ('kept@example.com', 'x', 1)"
            )
        )
        connection.execute(sa.text("DROP TABLE alembic_version"))

    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)

    with engine.connect() as connection:
        emails = connection.execute(sa.text("SELECT email FROM users")).scalars().all()
    engine.dispose()
    assert emails == ["kept@example.com"]


def test_upgrade_is_repeatable(alembic_cfg):
    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")


def test_downgrade_removes_the_schema(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(table_names(db_url))


def test_existing_users_become_read_only_when_roles_are_added(alembic_cfg, db_url):
    """Accounts that registered before roles existed must not silently gain privileges."""
    command.upgrade(alembic_cfg, "0001")
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users (email, hashed_password, is_active) "
                "VALUES ('old@example.com', 'x', 1)"
            )
        )

    command.upgrade(alembic_cfg, "head")

    with engine.connect() as connection:
        role = connection.execute(sa.text("SELECT role FROM users")).scalar_one()
    engine.dispose()
    assert role == "READ_ONLY"


# Old stored status -> workflow status after migration 0003
OLD_ROWS = [
    ("PENDING", None, "PENDING"),
    ("VALID", "2030-01-01", "FINAL"),
    ("VALID", None, "FINAL"),
    ("EXPIRING_SOON", "2026-11-01", "FINAL"),
    ("EXPIRED", "2020-01-01", "FINAL"),
]


def seed_old_compliance_rows(connection):
    connection.execute(sa.text("INSERT INTO products (name, model_number) VALUES ('P', 'M1')"))
    for number, (status, expiry, _) in enumerate(OLD_ROWS, start=1):
        connection.execute(
            sa.text(
                "INSERT INTO standards (standard_number, title, issuing_body, status) "
                "VALUES (:n, 'T', 'CSA', 'ACTIVE')"
            ),
            {"n": f"S{number}"},
        )
        connection.execute(
            sa.text(
                "INSERT INTO product_compliance (product_id, standard_id, status, expiration_date) "
                "VALUES (1, :standard, :status, :expiry)"
            ),
            {"standard": number, "status": status, "expiry": expiry},
        )


def test_certification_workflow_migration_converts_existing_records(alembic_cfg, db_url):
    """Pending stays Pending; every issued state becomes Final (validity is now computed)."""
    command.upgrade(alembic_cfg, "0002")
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        seed_old_compliance_rows(connection)

    command.upgrade(alembic_cfg, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT workflow_status, expiration_date FROM product_compliance ORDER BY id")
        ).all()
        columns = {c["name"] for c in sa.inspect(connection).get_columns("product_compliance")}
    engine.dispose()
    assert [r[0] for r in rows] == [expected for _, _, expected in OLD_ROWS]
    assert [r[1] for r in rows] == [expiry for _, expiry, _ in OLD_ROWS]  # dates untouched
    assert "status" not in columns
    assert {"workflow_status", "certificate_number", "issued_date", "agency"} <= columns


def test_certification_workflow_migration_downgrades_without_losing_dates(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "0003")  # this test is about 0003, which predates the unique key
    engine = sa.create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO products (name, model_number) VALUES ('P', 'M1')"))
        connection.execute(
            sa.text(
                "INSERT INTO standards (standard_number, title, issuing_body, status) "
                "VALUES ('S1', 'T', 'CSA', 'ACTIVE')"
            )
        )
        for workflow, expiry in [("DRAFT", None), ("FINAL", "2020-01-01"), ("FINAL", None)]:
            connection.execute(
                sa.text(
                    "INSERT INTO product_compliance "
                    "(product_id, standard_id, workflow_status, expiration_date) "
                    "VALUES (1, 1, :w, :e)"
                ),
                {"w": workflow, "e": expiry},
            )

    command.downgrade(alembic_cfg, "0002")

    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT status, expiration_date FROM product_compliance ORDER BY id")
        ).all()
    engine.dispose()
    assert [tuple(r) for r in rows] == [
        ("PENDING", None),
        ("EXPIRED", "2020-01-01"),
        ("VALID", None),
    ]


# --- PostgreSQL (the production database) ---
# Opt-in: set TEST_POSTGRES_URL to a throwaway database. CI does. It is deliberately NOT read
# from DATABASE_URL, so running the tests can never touch a real environment by accident. The
# test works inside its own temporary schema and drops it afterwards.
TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.mark.skipif(not TEST_POSTGRES_URL, reason="set TEST_POSTGRES_URL to run PostgreSQL tests")
def test_migrations_on_postgresql_convert_data_and_round_trip():
    schema = f"migration_test_{uuid.uuid4().hex[:12]}"
    base = make_url(TEST_POSTGRES_URL)
    scoped = base.update_query_dict({"options": f"-csearch_path={schema}"})

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option(
        "sqlalchemy.url", scoped.render_as_string(hide_password=False).replace("%", "%%")
    )

    admin = sa.create_engine(base)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(scoped)
    try:
        command.upgrade(cfg, "0002")
        with engine.begin() as connection:
            seed_old_compliance_rows(connection)

        command.upgrade(cfg, "head")
        command.check(cfg)  # the migrated schema matches the models on PostgreSQL too

        with engine.connect() as connection:
            workflow = (
                connection.execute(
                    sa.text("SELECT workflow_status::text FROM product_compliance ORDER BY id")
                )
                .scalars()
                .all()
            )
            enum_types = (
                connection.execute(
                    sa.text(
                        "SELECT t.typname FROM pg_type t "
                        "JOIN pg_namespace n ON n.oid = t.typnamespace "
                        "WHERE n.nspname = :schema "
                        "AND t.typname IN ('compliancestatus', 'workflowstatus')"
                    ),
                    {"schema": schema},
                )
                .scalars()
                .all()
            )
        assert workflow == [expected for _, _, expected in OLD_ROWS]
        assert enum_types == ["workflowstatus"]  # the old enum type is gone

        command.downgrade(cfg, "0002")
        with engine.connect() as connection:
            restored = (
                connection.execute(
                    sa.text("SELECT status::text FROM product_compliance ORDER BY id")
                )
                .scalars()
                .all()
            )
        assert restored == ["PENDING", "VALID", "VALID", "VALID", "EXPIRED"]

        command.upgrade(cfg, "head")  # and forward again
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
