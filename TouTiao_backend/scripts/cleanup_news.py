"""Remove known low-quality AI imports and optionally delete one exact title."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from config.db_conf import AsyncSessionLocal, async_engine
from models.news import News
from services.news_fetcher import BLOCKED_PHRASES


async def cleanup(exact_title: str | None) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(News))).scalars().all()
        removals = [
            row
            for row in rows
            if (exact_title and row.title == exact_title)
            or (
                row.is_ai_fetched
                and any(phrase in (row.title or "").lower() for phrase in BLOCKED_PHRASES)
            )
        ]
        for row in removals:
            print(f"delete id={row.id}: {row.title}")
            await db.delete(row)
        await db.commit()
        print(f"deleted={len(removals)}")
    await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", help="also remove an AI-fetched row with this exact title")
    args = parser.parse_args()
    asyncio.run(cleanup(args.title))
