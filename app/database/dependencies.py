from collections.abc import AsyncGenerator

from app.database.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator:
    async with AsyncSessionLocal() as session:
        yield session