#!/usr/bin/env python3
"""Phase 1.5 connectivity test: verify AsyncEngine and ORM against PostgreSQL."""

import asyncio
import sys

from sqlalchemy import select

from cuma_cloud.core.database import async_sessionmaker_factory
from cuma_cloud.models import CloudAccount


async def test_connection() -> None:
    async with async_sessionmaker_factory() as session:
        result = await session.execute(select(CloudAccount).limit(1))
        result.scalar_one_or_none()
    print("✅ Database connection and async ORM are working perfectly!")


def main() -> int:
    try:
        asyncio.run(test_connection())
        return 0
    except Exception as e:
        print(f"❌ Connection test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
