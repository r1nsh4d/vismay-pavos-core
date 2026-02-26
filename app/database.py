from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


def get_engine_kwargs() -> dict:
    if settings.DATABASE_URL.startswith("sqlite"):
        return {
            "echo": settings.DEBUG,
            "connect_args": {"check_same_thread": False},
        }
    return {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }


engine = create_async_engine(settings.DATABASE_URL, **get_engine_kwargs())

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── This is the key fix ───────────────────────────────────────────────────────
# SQLite doesn't support BIGINT autoincrement — use Integer in dev, BigInteger in prod
class Base(DeclarativeBase):
    pass


# Use this instead of BigInteger for all primary keys
def pk_type():
    """Returns Integer for SQLite, BigInteger for PostgreSQL"""
    if settings.DATABASE_URL.startswith("sqlite"):
        return Integer
    return BigInteger


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()