"""Tests verifying Alembic migration execution on fresh database."""

import os
import tempfile

from alembic import command
from alembic.config import Config


def test_alembic_migrations_upgrade_and_downgrade():
    """Verify Alembic migrations apply cleanly to head and downgrade to base."""
    # Use a temporary SQLite database file for testing migration execution
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        temp_db_path = tmp.name

    try:
        sqlite_url = f"sqlite+aiosqlite:///{temp_db_path}"

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)

        # Upgrade to head
        command.upgrade(alembic_cfg, "head")

        # Downgrade back to base
        command.downgrade(alembic_cfg, "base")

        # Re-upgrade to head
        command.upgrade(alembic_cfg, "head")
    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass
