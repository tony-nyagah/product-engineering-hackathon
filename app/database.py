from settings import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

engine = create_async_engine(
    settings.database_url,
    pool_size=5,  # 5 × 4 workers × 3 containers = 60 base connections
    max_overflow=10,  # 10 × 4 workers × 3 containers = 120 overflow; total 180 < pg max_connections=200
    pool_pre_ping=True,
    pool_timeout=20,  # fail fast instead of waiting 30 s (default) when pool is exhausted
    pool_recycle=300,  # recycle connections every 5 min to avoid stale TCP sessions
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
