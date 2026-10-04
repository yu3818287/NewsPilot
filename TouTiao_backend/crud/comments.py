from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import Comment
from models.users import User


async def create_comment(db: AsyncSession, news_id: int, user_id: int, content: str):
    comment = Comment(news_id=news_id, user_id=user_id, content=content.strip())
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    await db.commit()
    return comment


async def list_comments(db: AsyncSession, news_id: int, page: int, page_size: int):
    stmt = (
        select(Comment, User)
        .join(User, User.id == Comment.user_id)
        .where(Comment.news_id == news_id)
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    total = (
        await db.execute(select(func.count(Comment.id)).where(Comment.news_id == news_id))
    ).scalar_one()
    return rows, total


async def delete_comment(db: AsyncSession, comment_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(Comment).where(Comment.id == comment_id, Comment.user_id == user_id)
    )
    await db.commit()
    return result.rowcount > 0
