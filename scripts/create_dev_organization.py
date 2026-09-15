import asyncio

from app.database.session import AsyncSessionLocal
from app.services.organization_service import OrganizationService


async def main() -> None:
    async with AsyncSessionLocal() as db:
        organization = await OrganizationService.create_organization(
            db=db,
            name="Adaptive Interview Demo",
            slug="adaptive-interview-demo",
        )

        print(f"Organization created successfully.")
        print(f"ID: {organization.id}")
        print(f"Name: {organization.name}")
        print(f"Slug: {organization.slug}")
        print(f"Status: {organization.status}")


if __name__ == "__main__":
    asyncio.run(main())