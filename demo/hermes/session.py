"""Hermes 对话会话状态."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class HermesSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[ChatMessage] = Field(default_factory=list)
    last_scenario_id: str | None = None
    last_group: str | None = None
    tour_index: int = 0
    tour_active: bool = False

    def add_user(self, text: str) -> None:
        self.messages.append(ChatMessage(role="user", content=text))

    def add_assistant(
        self,
        text: str,
        intent: str = "",
        scenario_id: str | None = None,
        artifacts: list[dict] | None = None,
        suggestions: list[str] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            role="assistant",
            content=text,
            metadata={
                "intent": intent,
                "scenario_id": scenario_id,
                "artifacts": artifacts or [],
                "suggestions": suggestions or [],
            },
        )
        self.messages.append(msg)
        return msg

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        return [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "metadata": m.metadata,
            }
            for m in self.messages[-limit:]
        ]


class SessionStore:
    """内存会话存储（演示用）."""

    def __init__(self) -> None:
        self._sessions: dict[str, HermesSession] = {}

    def get_or_create(self, session_id: str | None = None) -> HermesSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session = HermesSession(session_id=session_id or uuid4().hex[:12])
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> HermesSession | None:
        return self._sessions.get(session_id)
