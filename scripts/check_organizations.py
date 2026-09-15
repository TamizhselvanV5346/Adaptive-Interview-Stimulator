import asyncio

from sqlalchemy import select

from app.database.models.organization import Organization
from app.database.session import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                Organization.id,
                Organization.name,
                Organization.slug,
                Organization.status,
            )
        )

        organizations = result.all()

        if not organizations:
            print("No organizations found.")
            return

        for organization in organizations:
            print(
                f"ID: {organization.id}\n"
                f"Name: {organization.name}\n"
                f"Slug: {organization.slug}\n"
                f"Status: {organization.status}\n"
            )


if __name__ == "__main__":
    asyncio.run(main())