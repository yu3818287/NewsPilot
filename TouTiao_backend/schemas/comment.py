from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    id: int
    news_id: int = Field(alias="newsId")
    user_id: int = Field(alias="userId")
    username: str
    nickname: str | None = None
    avatar: str | None = None
    content: str
    created_at: datetime = Field(alias="createdAt")
    is_mine: bool = Field(False, alias="isMine")

    model_config = {"populate_by_name": True}
