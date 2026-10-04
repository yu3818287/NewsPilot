import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AIChat


def _decode(value: str | None) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def list_conversations(db: AsyncSession, user_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(AIChat)
            .where(AIChat.user_id == user_id)
            .order_by(AIChat.created_at.desc(), AIChat.id.desc())
        )
    ).scalars().all()
    conversations: dict[str, dict] = {}
    for row in rows:
        item = conversations.get(row.conversation_id)
        if not item:
            item = {
                "id": row.conversation_id,
                "title": row.message[:36],
                "preview": row.response[:80],
                "createdAt": row.created_at.isoformat(),
                "updatedAt": row.created_at.isoformat(),
                "messageCount": 0,
            }
            conversations[row.conversation_id] = item
        # Rows are newest first, so repeated assignment leaves the first user
        # question as the stable conversation title and created timestamp.
        item["title"] = row.message[:36]
        item["createdAt"] = row.created_at.isoformat()
        item["messageCount"] += 2
    return list(conversations.values())


async def get_conversation(
    db: AsyncSession, user_id: int, conversation_id: str
) -> list[dict] | None:
    rows = (
        await db.execute(
            select(AIChat)
            .where(
                AIChat.user_id == user_id,
                AIChat.conversation_id == conversation_id,
            )
            .order_by(AIChat.created_at.asc(), AIChat.id.asc())
        )
    ).scalars().all()
    if not rows:
        return None
    messages = []
    for row in rows:
        messages.append(
            {
                "role": "user",
                "content": row.message,
                "createdAt": row.created_at.isoformat(),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": row.response,
                "sources": _decode(row.sources_json),
                "actions": _decode(row.actions_json),
                "createdAt": row.created_at.isoformat(),
            }
        )
    return messages


async def delete_conversation(db: AsyncSession, user_id: int, conversation_id: str) -> int:
    result = await db.execute(
        delete(AIChat).where(
            AIChat.user_id == user_id,
            AIChat.conversation_id == conversation_id,
        )
    )
    return result.rowcount or 0
