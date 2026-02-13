"""Migration script to add document columns to transfers table."""

from sqlalchemy import text
from app.database import engine


def migrate():
    """Add document columns to transfers table if they don't exist."""
    with engine.connect() as conn:
        # Check existing columns
        result = conn.execute(text("PRAGMA table_info(transfers)"))
        columns = [row[1] for row in result.fetchall()]

        # Add new columns if they don't exist
        if 'documento_emision_path' not in columns:
            conn.execute(text(
                "ALTER TABLE transfers ADD COLUMN documento_emision_path VARCHAR(500)"
            ))
            print("Added column: documento_emision_path")

        if 'documento_emision_filename' not in columns:
            conn.execute(text(
                "ALTER TABLE transfers ADD COLUMN documento_emision_filename VARCHAR(255)"
            ))
            print("Added column: documento_emision_filename")

        if 'documento_recepcion_path' not in columns:
            conn.execute(text(
                "ALTER TABLE transfers ADD COLUMN documento_recepcion_path VARCHAR(500)"
            ))
            print("Added column: documento_recepcion_path")

        if 'documento_recepcion_filename' not in columns:
            conn.execute(text(
                "ALTER TABLE transfers ADD COLUMN documento_recepcion_filename VARCHAR(255)"
            ))
            print("Added column: documento_recepcion_filename")

        conn.commit()
        print("Migration completed successfully.")


if __name__ == "__main__":
    migrate()
