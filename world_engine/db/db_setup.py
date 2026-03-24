"""
Database Setup Module for World Engine

This module provides async SQLite database operations using aiosqlite.
All operations are non-blocking and safe for use within an asyncio event loop.
"""

import aiosqlite
from pathlib import Path


async def init_database(db_path: str = "world_engine.db") -> None:
    """
    Initialize the SQLite database with the room_states table.

    This function creates the database file if it doesn't exist and
    sets up the schema for persisting room states.

    Args:
        db_path: Path to the SQLite database file
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS room_states (
                room_id TEXT PRIMARY KEY,
                last_temp REAL NOT NULL,
                last_humidity REAL NOT NULL,
                hvac_mode TEXT NOT NULL DEFAULT 'off',
                target_temp REAL NOT NULL DEFAULT 22.0,
                last_update INTEGER NOT NULL
            )
        """)

        # Create index for faster queries by update time
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_room_states_last_update
            ON room_states(last_update)
        """)

        await db.commit()
        print(f"Database initialized at: {Path(db_path).absolute()}")


async def upsert_room_state(
    db: aiosqlite.Connection,
    room_id: str,
    temp: float,
    humidity: float,
    hvac_mode: str,
    target_temp: float,
    timestamp: int
) -> None:
    """
    Insert or update a room's state in the database.

    Uses SQLite's INSERT OR REPLACE for atomic upsert operations.
    This is non-blocking and safe for concurrent access.

    Args:
        db: Active aiosqlite connection
        room_id: Unique room identifier (e.g., "b01-f05-r202")
        temp: Current temperature reading
        humidity: Current humidity reading
        hvac_mode: Current HVAC mode ("on", "off", "eco")
        target_temp: Target temperature setpoint
        timestamp: Unix timestamp of the update
    """
    await db.execute("""
        INSERT OR REPLACE INTO room_states
        (room_id, last_temp, last_humidity, hvac_mode, target_temp, last_update)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (room_id, temp, humidity, hvac_mode, target_temp, timestamp))
    # Note: Commit is handled at batch level for performance


async def get_room_state(db: aiosqlite.Connection, room_id: str) -> dict | None:
    """
    Retrieve a room's persisted state from the database.

    Args:
        db: Active aiosqlite connection
        room_id: Unique room identifier

    Returns:
        Dictionary with room state or None if not found
    """
    async with db.execute(
        "SELECT * FROM room_states WHERE room_id = ?", (room_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return {
                "room_id": row[0],
                "last_temp": row[1],
                "last_humidity": row[2],
                "hvac_mode": row[3],
                "target_temp": row[4],
                "last_update": row[5]
            }
    return None


async def batch_commit(db: aiosqlite.Connection) -> None:
    """
    Commit pending database transactions.

    Called periodically to batch multiple updates into a single disk write,
    improving performance when many rooms update simultaneously.
    """
    await db.commit()


# Standalone execution for initial setup
if __name__ == "__main__":
    import asyncio
    asyncio.run(init_database())
    print("Database setup complete!")
