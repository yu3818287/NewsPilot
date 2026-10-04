from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud import comments
from crud.news import get_news_detail
from models.users import User
from schemas.comment import CommentCreateRequest
from utils.auth import get_current_user, get_optional_user
from utils.response import success_response


router = APIRouter(prefix="/api/news", tags=["comments"])


def _serialize(comment, author, current_user_id: int | None):
    return {
        "id": comment.id,
        "newsId": comment.news_id,
        "userId": comment.user_id,
        "username": author.username,
        "nickname": author.nickname,
        "avatar": author.avatar,
        "content": comment.content,
        "createdAt": comment.created_at,
        "isMine": comment.user_id == current_user_id,
    }


@router.get("/{news_id}/comments")
async def get_comments(
    news_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await comments.list_comments(db, news_id, page, page_size)
    return success_response(
        data={
            "list": [_serialize(comment, author, user.id if user else None) for comment, author in rows],
            "total": total,
            "hasMore": page * page_size < total,
        }
    )


@router.post("/{news_id}/comments")
async def add_comment(
    news_id: int,
    payload: CommentCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await get_news_detail(db, news_id):
        raise HTTPException(status_code=404, detail="新闻不存在")
    comment = await comments.create_comment(db, news_id, user.id, payload.content)
    return success_response("评论成功", _serialize(comment, user, user.id))


@router.delete("/comments/{comment_id}")
async def remove_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await comments.delete_comment(db, comment_id, user.id):
        raise HTTPException(status_code=404, detail="评论不存在或无权删除")
    return success_response("评论已删除")
