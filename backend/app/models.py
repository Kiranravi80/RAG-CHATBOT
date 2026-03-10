from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Natural language question")
    session_id: str = Field(..., min_length=4, description="Client conversation session id")


class QueryResponse(BaseModel):
    session_id: str
    question: str
    generated_sql: str
    summary: str
    rows: list[dict[str, Any]]
    columns: list[str]
    chart: dict[str, Any] | None = None
    dashboard: dict[str, Any] | None = None
    sources: list[str] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HistoryResponse(BaseModel):
    session_id: str
    items: list[QueryResponse]


class SessionSummary(BaseModel):
    session_id: str
    turns: int
    last_question: str
    last_created_at: str


class SessionsResponse(BaseModel):
    sessions: list[SessionSummary]
