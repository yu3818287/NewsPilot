from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=12000)


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = Field(None, alias="conversationId", max_length=64)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)

    model_config = {"populate_by_name": True}


class NewsSource(BaseModel):
    id: int
    title: str
    source: str | None = None
    source_url: str | None = Field(None, alias="sourceUrl")
    publish_time: str = Field(alias="publishTime")

    model_config = {"populate_by_name": True}


class AIChatResponse(BaseModel):
    answer: str
    conversation_id: str = Field(alias="conversationId")
    sources: list[NewsSource] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    model: str

    model_config = {"populate_by_name": True}


class NewsSyncRequest(BaseModel):
    query: str = Field("2026 最新新闻", max_length=100)
    limit: int = Field(12, ge=1, le=30)
