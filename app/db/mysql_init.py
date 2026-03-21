from __future__ import annotations

from sqlalchemy import text

from app.db.engine import get_app_engine


def ensure_app_database_exists() -> None:
    """Initialize the app storage schema on the configured database."""
    # App tables are created through SQLAlchemy metadata.create_all().
    # This helper is kept as an explicit extension point for future MySQL bootstrap work.
    engine = get_app_engine()
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))

