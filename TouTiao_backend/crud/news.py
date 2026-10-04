from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from models.news import Category, News
from models.history import History
from sqlalchemy import and_, case, func, or_, select, update


async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(Category).order_by(Category.sort_order, Category.id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_news_list(db: AsyncSession, category_id: int, skip: int = 0, limit: int = 10):
    category = await db.get(Category, category_id)
    if category and category.name == "AI推荐":
        return await get_ai_recommendations(db, skip, limit)
    stmt = (
        select(News)
        .where(News.category_id == category_id)
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_news_count(db: AsyncSession, category_id: int):
    category = await db.get(Category, category_id)
    if category and category.name == "AI推荐":
        cutoff = max(datetime(2026, 1, 1), datetime.now() - timedelta(days=14))
        stmt = select(func.count(News.id)).where(News.publish_time >= cutoff)
        result = await db.execute(stmt)
        return result.scalar_one()
    # 查询的是指定分类下的新闻数量
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    result = await db.execute(stmt)
    return result.scalar_one()  # 只能有一个结果，否则报错


async def get_ai_recommendations(db: AsyncSession, skip: int = 0, limit: int = 10):
    """Rank 2026 domestic/world news by last-24-hour reads, total reads, then freshness."""
    preferred_category = case((News.category_id.in_([3, 4]), 1), else_=0)
    has_image = case((News.image.is_not(None), 1), else_=0)
    since = datetime.now() - timedelta(hours=24)
    cutoff = max(datetime(2026, 1, 1), datetime.now() - timedelta(days=14))
    stmt = (
        select(News)
        .outerjoin(
            History,
            and_(History.news_id == News.id, History.view_time >= since),
        )
        .where(News.publish_time >= cutoff)
        .group_by(News.id)
        .order_by(
            preferred_category.desc(),
            has_image.desc(),
            func.count(History.id).desc(),
            News.views.desc(),
            News.publish_time.desc(),
        )
        .offset(0)
        .limit((skip + limit) * 3)
    )
    result = await db.execute(stmt)
    deduplicated = []
    seen_titles = set()
    for item in result.scalars().all():
        normalized = "".join(item.title.lower().split())
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        deduplicated.append(item)
    return deduplicated[skip:skip + limit]


async def search_news(
    db: AsyncSession,
    keywords: list[str],
    limit: int = 100,
    category_ids: list[int] | None = None,
):
    conditions = []
    for keyword in keywords[:8]:
        pattern = f"%{keyword}%"
        conditions.append(
            or_(News.title.like(pattern), News.description.like(pattern), News.content.like(pattern))
        )
    stmt = select(News).where(News.publish_time >= "2026-01-01")
    if conditions:
        stmt = stmt.where(or_(*conditions))
    if category_ids:
        stmt = stmt.where(News.category_id.in_(category_ids))
    stmt = stmt.order_by(News.publish_time.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_recent_news(db: AsyncSession, limit: int = 400):
    stmt = (
        select(News)
        .where(News.publish_time >= "2026-01-01")
        .order_by(News.publish_time.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_news_detail(db: AsyncSession, news_id: int):
    stmt = select(News).where(News.id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def increase_news_views(db: AsyncSession, news_id: int):
    stmt = update(News).where(News.id == news_id).values(views=News.views + 1)
    result = await db.execute(stmt)
    await db.commit()

    # 更新 → 检查数据库是否真的命中了数据 → 命中了返回True
    return result.rowcount > 0


async def get_related_news(db: AsyncSession, news_id: int, category_id: int, limit: int = 5):
    # order_by 排序 → 浏览量和发布时间
    stmt = select(News).where(
        News.category_id == category_id,
        News.id != news_id
    ).order_by(
        News.views.desc(),  # 默认是升序，desc 表示降序
        News.publish_time.desc()
    ).limit(limit)
    result = await db.execute(stmt)
    # return result.scalars().all()
    related_news = result.scalars().all()
    # 列表推导式 推导出新闻的核心数据，然后再 return
    return [{
        "id": news_detail.id,
        "title": news_detail.title,
        "content": news_detail.content,
        "image": news_detail.image,
        "author": news_detail.author,
        "publishTime": news_detail.publish_time,
        "categoryId": news_detail.category_id,
        "views": news_detail.views
    } for news_detail in related_news]
