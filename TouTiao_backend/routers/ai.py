from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from config.settings import settings
from crud import ai_chat as ai_chat_crud
from models.users import User
from schemas.ai import AIChatRequest, NewsSyncRequest
from services.news_agent import run_news_agent
from services.news_fetcher import fetch_and_store
from utils.auth import get_current_user, get_optional_user
from utils.response import success_response


router = APIRouter(prefix="/api/ai", tags=["ai-agent"])


@router.post("/conversations")
async def create_conversation(_user: User = Depends(get_current_user)):
    return success_response("新对话已创建", {"conversationId": uuid4().hex})


@router.get("/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversations = await ai_chat_crud.list_conversations(db, user.id)
    return success_response(data={"list": conversations, "total": len(conversations)})


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await ai_chat_crud.get_conversation(db, user.id, conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="对话不存在或无权访问")
    return success_response(data={"conversationId": conversation_id, "messages": messages})


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await ai_chat_crud.delete_conversation(db, user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="对话不存在或无权访问")
    await db.commit()
    return success_response("对话已删除", {"deleted": deleted})


@router.post("/chat")
async def chat_with_news_agent(
    payload: AIChatRequest,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await run_news_agent(
        db=db,
        query=payload.message,
        history=[item.model_dump() for item in payload.history],
        user_id=user.id if user else None,
        conversation_id=payload.conversation_id,
    )
    # Make an immediate history refresh deterministic. Dependency finalizers
    # can otherwise commit only after the response has already reached Vue.
    await db.commit()
    return success_response("AI 新闻代理已完成", result)


@router.post("/sync-news")
async def sync_news(
    payload: NewsSyncRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    saved = await fetch_and_store(db, payload.query, payload.limit)
    return success_response(
        f"已同步或更新 {len(saved)} 条 {settings.news_year} 年新闻",
        {"updated": len(saved), "ids": [item.id for item in saved]},
    )


@router.get("/status")
async def ai_status():
    return success_response(
        data={
            "model": settings.deepseek_model,
            "configured": bool(settings.deepseek_api_key),
            "newsYear": settings.news_year,
            "framework": "LangGraph + BM25 RAG",
        }
    )
