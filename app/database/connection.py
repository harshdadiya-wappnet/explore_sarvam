from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import os
from dotenv import load_dotenv
load_dotenv()


port = os.getenv("DATABASE_PORT")
DATABASE_URL = URL.create(
    drivername=os.getenv("DATABASE_DRIVER"),  # asyncpg
    database=os.getenv("DATABASE_NAME"),
    host=os.getenv("DATABASE_HOST"),
    port=int(port) if port else None,
    username=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PASSWORD"),
)

SYNC_DATABASE_URL = URL.create(
    drivername=os.getenv("DATABASE_DRIVER_SYNC"),  # psycopg
    database=os.getenv("DATABASE_NAME"),
    host=os.getenv("DATABASE_HOST"),
    port=int(port) if port else None,
    username=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PASSWORD"),
)

engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None

# Create a base class for our models
Base = declarative_base()

__all__ = ["Base", "SessionLocal", "init_db", "get_db", "DATABASE_URL", "SYNC_DATABASE_URL"]


def _get_engine() -> AsyncEngine:
    global engine
    if engine is None:
        engine = create_async_engine(url=DATABASE_URL)
    return engine


def _get_session_local() -> async_sessionmaker[AsyncSession]:
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return SessionLocal

async def init_db() -> None:
    """Initialize the database by creating all tables defined in the models.
    
    This function should be called during application startup to ensure
    all required database tables exist.
    
    Raises:
        Exception: If database connection or table creation fails
    """
    try:
        print("Connecting to the database and ensuring tables are created")
        # Run metadata creation via async engine connection.
        async with _get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Failed to connect to the database or create tables: {str(e)}")
        raise  # Re-raise the exception to prevent the app from starting if the database setup fails


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.
    
    This is a dependency function that provides a database session
    and ensures it is properly closed after use.
    
    Yields:
        AsyncSession: An async SQLAlchemy database session
    """
    session_factory = _get_session_local()
    async with session_factory() as db:
        yield db
