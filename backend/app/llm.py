from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from groq import Groq

from app.config import settings
from app.prompts import (
    DIMENSION_EXPAND_PROMPT,
    DASHBOARD_PROMPT,
    FINAL_RESPONSE_PROMPT,
    FORCE_ENTITY_COLUMNS_PROMPT,
    NL_TO_SQL_SYSTEM_PROMPT,
    NO_RESULT_REWRITE_PROMPT,
    RESULT_SHAPE_REWRITE_PROMPT,
    SQL_REPAIR_SYSTEM_PROMPT,
)


class GroqClient:
    def __init__(self) -> None:
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def _clean_sql(self, text: str) -> str:
        cleaned = text.strip()
        fenced = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1).strip()
        return cleaned.rstrip(";")

    def _history_text(self, history: list[dict[str, Any]]) -> str:
        if not history:
            return "No prior conversation."
        lines: list[str] = []
        for i, turn in enumerate(history[-8:], start=1):
            lines.append(f"Turn {i} user: {turn.get('question', '')}")
            lines.append(f"Turn {i} sql: {turn.get('generated_sql', '')}")
            lines.append(f"Turn {i} summary: {turn.get('summary', '')}")
        return "\n".join(lines)

    def _to_json_safe(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return {k: self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [self._to_json_safe(v) for v in value]
        return value

    def generate_sql(self, question: str, context_docs: list[str], history: list[dict[str, Any]]) -> str:
        context = "\n".join(context_docs[:120])
        history_text = self._history_text(history)
        msg = (
            f"Conversation history:\n{history_text}\n\n"
            f"Question:\n{question}\n\n"
            f"Schema and relationship context:\n{context}\n\n"
            "Return SQL now."
        )
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.05,
            messages=[
                {"role": "system", "content": NL_TO_SQL_SYSTEM_PROMPT},
                {"role": "user", "content": msg},
            ],
        )
        sql = completion.choices[0].message.content or ""
        return self._clean_sql(sql)

    def repair_sql(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        context_docs: list[str],
        history: list[dict[str, Any]],
    ) -> str:
        context = "\n".join(context_docs[:140])
        history_text = self._history_text(history)
        msg = (
            f"Question:\n{question}\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Failed SQL:\n{failed_sql}\n\n"
            f"Database error:\n{error_message}\n\n"
            f"Schema and relationship context:\n{context}\n\n"
            "Return corrected SQL now."
        )
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": SQL_REPAIR_SYSTEM_PROMPT},
                {"role": "user", "content": msg},
            ],
        )
        repaired = completion.choices[0].message.content or ""
        return self._clean_sql(repaired)

    def rewrite_sql_for_no_results(
        self,
        question: str,
        sql: str,
        context_docs: list[str],
        history: list[dict[str, Any]],
    ) -> str:
        context = "\n".join(context_docs[:120])
        history_text = self._history_text(history)
        msg = (
            f"Question:\n{question}\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Original SQL (returned zero rows):\n{sql}\n\n"
            f"Schema and relationship context:\n{context}\n\n"
            "Return rewritten SQL now."
        )
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": NO_RESULT_REWRITE_PROMPT},
                {"role": "user", "content": msg},
            ],
        )
        rewritten = completion.choices[0].message.content or ""
        return self._clean_sql(rewritten)

    def expand_sql_dimensions(
        self,
        question: str,
        sql: str,
        requested_entities: list[str],
        context_docs: list[str],
        history: list[dict[str, Any]],
    ) -> str:
        if not requested_entities:
            return sql
        context = "\n".join(context_docs[:140])
        history_text = self._history_text(history)
        entities = ", ".join(requested_entities)
        msg = (
            f"Question:\n{question}\n\n"
            f"Requested entities:\n{entities}\n\n"
            f"Current SQL:\n{sql}\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Schema and relationship context:\n{context}\n\n"
            "Return improved SQL now."
        )
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": DIMENSION_EXPAND_PROMPT},
                {"role": "user", "content": msg},
            ],
        )
        improved = completion.choices[0].message.content or ""
        return self._clean_sql(improved)

    def rewrite_sql_for_result_shape(
        self,
        question: str,
        sql: str,
        missing_entities: list[str],
        context_docs: list[str],
        history: list[dict[str, Any]],
    ) -> str:
        context = "\n".join(context_docs[:140])
        history_text = self._history_text(history)
        missing = ", ".join(missing_entities)
        msg = (
            f"Question:\n{question}\n\n"
            f"Missing entities in current result:\n{missing}\n\n"
            f"Current SQL:\n{sql}\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Schema and relationship context:\n{context}\n\n"
            "Return rewritten SQL now."
        )
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": RESULT_SHAPE_REWRITE_PROMPT},
                {"role": "user", "content": msg},
            ],
        )
        rewritten = completion.choices[0].message.content or ""
        return self._clean_sql(rewritten)

    def force_sql_with_entities(
        self,
        question: str,
        entities: list[str],
        context_docs: list[str],
        history: list[dict[str, Any]],
    ) -> str:
        context = "\n".join(context_docs[:160])
        history_text = self._history_text(history)
        requested = ", ".join(entities)
        msg = (
            f"Question:\n{question}\n\n"
            f"Requested entities:\n{requested}\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Schema and relationship context:\n{context}\n\n"
            "Return SQL now."
        )
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": FORCE_ENTITY_COLUMNS_PROMPT},
                {"role": "user", "content": msg},
            ],
        )
        forced = completion.choices[0].message.content or ""
        return self._clean_sql(forced)

    def summarize_result(
        self,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        want_chart: bool,
        history: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any] | None]:
        payload = {
            "question": question,
            "sql": sql,
            "want_chart": want_chart,
            "history": self._to_json_safe(history[-6:]),
            "rows": self._to_json_safe(rows[:200]),
        }
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FINAL_RESPONSE_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return "Summary generation failed for this result.", None
        summary = parsed.get("summary", "No summary available.")
        chart = parsed.get("chart") if want_chart else None
        return summary, chart

    def generate_dashboard(self, question: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        datasets: list[dict[str, Any]] = []
        for turn in history[-10:]:
            rows = turn.get("rows") or []
            columns = turn.get("columns") or []
            if rows and columns:
                datasets.append(
                    {
                        "question": turn.get("question", ""),
                        "summary": turn.get("summary", ""),
                        "columns": columns,
                        "rows": self._to_json_safe(rows[:100]),
                    }
                )
        if not datasets:
            return {
                "title": "Dashboard",
                "description": "No prior datasets available. Ask a data query first, then request dashboard.",
                "kpis": [],
                "charts": [],
            }

        payload = {
            "question": question,
            "datasets": datasets,
        }
        completion = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": DASHBOARD_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "title": "Dashboard",
                "description": "Dashboard generation failed to parse model output.",
                "kpis": [],
                "charts": [],
            }

        parsed.setdefault("title", "Dashboard")
        parsed.setdefault("description", "Auto-generated dashboard")
        parsed.setdefault("kpis", [])
        parsed.setdefault("charts", [])
        return parsed
