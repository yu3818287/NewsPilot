"""Manually run the same live-news ingestion used by the background scheduler."""

import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.db_conf import AsyncSessionLocal, async_engine
from services.news_fetcher import fetch_and_store, sync_default_feeds


async def main(query: str | None, limit: int):
    async with AsyncSessionLocal() as session:
        if query:
            count = len(await fetch_and_store(session, query, limit))
        else:
            count = await sync_default_feeds(session)
        await session.commit()
        print(f"saved={count}")
    await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="同步并丰富实时新闻")
    parser.add_argument("query", nargs="?", help="可选的新闻检索主题")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    asyncio.run(main(args.query, max(1, min(args.limit, 20))))
