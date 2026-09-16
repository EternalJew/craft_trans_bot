"""Add columns that appeared after a table was first created.

SQLAlchemy's create_all only ever creates missing tables, so a new column on an
existing table is invisible to it. Once there are real bookings the database can
no longer just be recreated, so new columns are added here instead.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# table -> column -> the DDL used to add it
ADDED_COLUMNS = {
    "bookings": {
        "book_status":     "VARCHAR DEFAULT 'pending'",
        "book_written_at": "DATETIME",
        "van_no":          "INTEGER",
    },
    "notifications": {
        "entity_id": "INTEGER",
    },
}


def run(engine: Engine) -> list[str]:
    applied = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for column, ddl in columns.items():
                if column in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                applied.append(f"{table}.{column}")
    return applied
