from __future__ import annotations

import json
from datetime import datetime
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from crud import news as news_crud
from models.ai import AIChat
from models.news import News
from services.deepseek import DeepSeekError, chat
from services.news_fetcher import fetch_and_store
from services.rag import bm25_rank, tokenize


LIVE_HINTS = (
    "最新", "今天", "今日", "刚刚", "实时", "当日", "本周", "2026", "current", "latest", "today"
)
LOW_QUALITY_PHRASES = (
    "真人娱乐", "博彩", "投注平台", "pg胜天", "app下载最新版", "游戏大厅", "娱乐平台",
    "黑科网", "独家新闻官方版", "安卓网"
)


class AgentState(TypedDict, total=False):
    query: str
    history: list[dict]
    needs_web: bool
    fetched: list[News]
    context: list[News]
    answer: str
    actions: list[str]


def _needs_live_news(query: str) -> bool:
    return any(hint in query.lower() for hint in LIVE_HINTS)


def _is_general_latest_request(query: str) -> bool:
    topic_hints = ("人工智能", "ai", "科技", "财经", "体育", "娱乐", "军事", "汽车", "教育", "医疗")
    return _needs_live_news(query) and not any(hint in query.lower() for hint in topic_hints)


def _is_rag_ready(item: News) -> bool:
    """Keep the answer grounded in substantial local copy, not thin feed snippets."""
    title = (item.title or "").lower()
    content = (item.content or "").strip()
    return len(content) >= 300 and not any(phrase in title for phrase in LOW_QUALITY_PHRASES)


def _context_block(items: list[News]) -> str:
    blocks = []
    for index, item in enumerate(items, 1):
        blocks.append(
            f"[{index}] 新闻ID={item.id}\n"
            f"标题：{item.title}\n"
            f"来源：{item.source_name or item.author or '未知'}\n"
            f"时间：{item.publish_time:%Y-%m-%d %H:%M}\n"
            f"摘要：{item.description or item.content[:400]}\n"
            f"原文：{item.source_url or '本地历史新闻'}"
        )
    return "\n\n".join(blocks)


def build_news_agent(db: AsyncSession):
    async def plan(state: AgentState) -> AgentState:
        needs_web = _needs_live_news(state["query"])
        actions = ["识别用户新闻需求"]
        if needs_web:
            actions.append("检索 2026 年实时公开新闻源")
        return {"needs_web": needs_web, "actions": actions}

    def route_after_plan(state: AgentState) -> str:
        return "live_search" if state.get("needs_web") else "retrieve"

    async def live_search(state: AgentState) -> AgentState:
        try:
            fetched = await fetch_and_store(db, state["query"], 15)
            action = f"实时同步并更新 {len(fetched)} 条新闻到本地数据库"
            return {"fetched": fetched, "actions": [*state.get("actions", []), action]}
        except Exception as exc:
            await db.rollback()
            return {
                "fetched": [],
                "actions": [*state.get("actions", []), f"实时源暂不可用，改用本地 RAG（{type(exc).__name__}）"],
            }

    async def retrieve(state: AgentState) -> AgentState:
        documents = await news_crud.get_recent_news(db, 500)
        rich_documents = [item for item in documents if _is_rag_ready(item)]
        if rich_documents:
            documents = rich_documents
        fetched = state.get("fetched", [])
        fetched = [item for item in fetched if _is_rag_ready(item)]
        if _is_general_latest_request(state["query"]):
            unique = {item.id: item for item in [*documents, *fetched]}
            context = sorted(
                unique.values(), key=lambda item: item.publish_time, reverse=True
            )[:8]
        elif fetched:
            fetched_ids = {item.id for item in fetched}
            related = bm25_rank(
                state["query"], [item for item in documents if item.id not in fetched_ids], 8
            )
            context = [*sorted(fetched, key=lambda item: item.publish_time, reverse=True), *related][:8]
        else:
            context = bm25_rank(state["query"], documents, 8)
        if not context:
            context = documents[:8]
        return {
            "context": context,
            "actions": [*state.get("actions", []), f"RAG 召回 {len(context)} 条相关新闻"],
        }

    async def answer(state: AgentState) -> AgentState:
        context = state.get("context", [])
        system = (
            "你是新闻资讯应用中的 AI 新闻编辑。只依据给定的新闻资料回答；无法从资料确认的事实要明确说明。"
            "优先回应用户的筛选条件，结果用简洁中文，推荐新闻时列出标题、时间、来源和推荐理由，"
            "并用 [1] 这样的编号引用资料。不得编造网址、事件或日期。"
            f"当前日期：{datetime.now():%Y-%m-%d}，数据库只把 {settings.news_year} 年内容视为最新新闻。"
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(state.get("history", [])[-8:])
        messages.append(
            {
                "role": "user",
                "content": f"用户问题：{state['query']}\n\n可用新闻资料：\n{_context_block(context)}",
            }
        )
        try:
            response = await chat(messages)
        except DeepSeekError as exc:
            if context:
                lines = ["AI 服务暂时不可用，先为你列出检索结果："]
                lines.extend(
                    f"- [{index}] {item.title}（{item.publish_time:%Y-%m-%d}，{item.source_name or item.author or '未知来源'}）"
                    for index, item in enumerate(context, 1)
                )
                response = "\n".join(lines) + f"\n\n服务信息：{exc}"
            else:
                response = f"AI 服务暂时不可用：{exc}"
        return {"answer": response}

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("live_search", live_search)
    graph.add_node("retrieve", retrieve)
    graph.add_node("answer", answer)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route_after_plan, {"live_search": "live_search", "retrieve": "retrieve"})
    graph.add_edge("live_search", "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


async def run_news_agent(
    db: AsyncSession,
    query: str,
    history: list[dict],
    user_id: int | None,
    conversation_id: str | None,
) -> dict:
    conversation_id = conversation_id or uuid4().hex
    result = await build_news_agent(db).ainvoke({"query": query, "history": history})
    context: list[News] = result.get("context", [])
    sources = [
        {
            "id": item.id,
            "title": item.title,
            "source": item.source_name or item.author,
            "sourceUrl": item.source_url,
            "publishTime": item.publish_time.isoformat(),
        }
        for item in context
    ]
    actions = result.get("actions", [])
    if user_id:
        db.add(
            AIChat(
                user_id=user_id,
                conversation_id=conversation_id,
                message=query,
                response=result["answer"],
                sources_json=json.dumps(sources, ensure_ascii=False),
                actions_json=json.dumps(actions, ensure_ascii=False),
            )
        )
        await db.flush()
    return {
        "answer": result["answer"],
        "conversationId": conversation_id,
        "sources": sources,
        "actions": actions,
        "model": settings.deepseek_model,
    }
