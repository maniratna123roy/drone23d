import asyncpg
from backend.config import settings

# Global pool variable
pool: asyncpg.Pool | None = None

async def connect_to_db() -> bool:
    global pool
    try:
        pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=10)
        print("Successfully connected to PostGIS database.")
        return True
    except Exception as e:
        print(f"[WARN] Could not connect to PostGIS at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}: {e}")
        print("[INFO] PostGIS container may be offline. Start it with: docker compose up -d db")
        pool = None
        return False

async def close_db_connection():
    global pool
    if pool:
        await pool.close()
        print("Database connection closed.")
        pool = None

async def ensure_db_connected() -> bool:
    global pool
    if pool is not None and not pool.is_closing():
        return True
    return await connect_to_db()

def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized. PostGIS container is offline. Run 'docker compose up -d db' to start it.")
    return pool
