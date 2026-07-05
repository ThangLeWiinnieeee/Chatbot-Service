"""HTTP routes: POST /api/chat."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ..core.engine import ChatEngine
from ..core.types import ChatContext, Message
from .deps import get_engine, verify_secret

router = APIRouter(prefix="/api", tags=["chat"])


class MessageIn(BaseModel):
    role: str = Field(description="user | assistant")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Câu hỏi của người dùng")
    history: list[MessageIn] = Field(default_factory=list)
    user: dict | None = None
    sessionId: str | None = None


class ChatResponse(BaseModel):
    answer: str
    source: str
    intent: str | None = None
    confidence: float
    suggestions: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


def _bearer(authorization: str | None) -> str | None:
    """Bóc token từ header 'Authorization: Bearer <token>'."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_secret)])
async def chat(
    payload: ChatRequest,
    engine: ChatEngine = Depends(get_engine),
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    ctx = ChatContext(
        history=[Message(role=m.role, content=m.content) for m in payload.history],
        user=payload.user,
        session_id=payload.sessionId,
        auth_token=_bearer(authorization),
    )
    result = await engine.answer(payload.message, ctx)
    return ChatResponse(
        answer=result.answer,
        source=result.source,
        intent=result.intent,
        confidence=result.confidence,
        suggestions=result.suggestions,
        meta=result.meta,
    )
