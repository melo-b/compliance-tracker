from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

import app.models  # noqa: F401
from app.db.base import Base

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


def test_upgrade_adopts_a_database_created_by_create_all(alembic_cfg, db_url):
    """The live demo database was built by create_all(); upgrading it must not fail."""
    engine = sa.create_engine(db_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)


def test_upgrade_is_repeatable(alembic_cfg):
    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")


def test_downgrade_removes_the_schema(alembic_cfg, db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(table_names(db_url))
