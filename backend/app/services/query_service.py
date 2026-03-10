from __future__ import annotations

import re

from app.database import DatabaseClient
from app.llm import GroqClient
from app.memory import MemoryStore
from app.models import QueryResponse
from app.rag import RagStore


CHART_HINTS = ("graph", "chart", "plot", "visualize", "bar", "line", "pie")
DASHBOARD_HINTS = ("dashboard", "kpi board", "scorecard")
ENTITY_HINTS = ("product", "customer", "order", "category", "supplier", "user", "payment", "cart")
ENTITY_COLUMN_HINTS = {
    "product": ("product", "item"),
    "category": ("category", "cat"),
    "user": ("user", "customer", "name"),
    "customer": ("customer", "name"),
    "order": ("order",),
    "supplier": ("supplier", "vendor"),
    "payment": ("payment", "amount"),
    "cart": ("cart",),
}


class QueryService:
    def __init__(self) -> None:
        self.db = DatabaseClient()
        self.rag = RagStore()
        self.llm = GroqClient()
        self.memory = MemoryStore(max_turns=40)

    def startup(self, knowledge_path: str) -> None:
        schema_docs = self.db.load_schema_docs()
        self.rag.build(schema_docs, knowledge_path)

    def _wants_chart(self, question: str) -> bool:
        lowered = question.lower()
        return any(k in lowered for k in CHART_HINTS)

    def _wants_dashboard(self, question: str) -> bool:
        lowered = question.lower()
        return any(k in lowered for k in DASHBOARD_HINTS)

    def _extract_entities(self, question: str) -> list[str]:
        lowered = question.lower()
        found: list[str] = []
        for entity in ENTITY_HINTS:
            if re.search(rf"\b{re.escape(entity)}s?\b", lowered):
                found.append(entity)
        return found

    def _augment_context(self, question: str, ctx: list[str]) -> list[str]:
        docs = list(ctx)
        all_docs = getattr(self.rag, "docs", [])
        entities = self._extract_entities(question)
        if not entities:
            return docs

        for entity in entities:
            for line in all_docs:
                low = line.lower()
                if (
                    f"table={entity}" in low
                    or f"table={entity}s" in low
                    or f"from={entity}." in low
                    or f"to={entity}." in low
                    or f"from={entity}s." in low
                    or f"to={entity}s." in low
                ) and line not in docs:
                    docs.append(line)

        return docs[:140]

    def _missing_entities_in_columns(self, entities: list[str], columns: list[str]) -> list[str]:
        if not entities:
            return []
        lowered_cols = [c.lower() for c in columns]
        missing: list[str] = []
        for entity in entities:
            hints = ENTITY_COLUMN_HINTS.get(entity, (entity,))
            if not any(any(h in c for h in hints) for c in lowered_cols):
                missing.append(entity)
        return missing

    def get_history(self, session_id: str) -> list[QueryResponse]:
        return [QueryResponse(**item) for item in self.memory.get(session_id)]

    def clear_history(self, session_id: str) -> None:
        self.memory.clear(session_id)

    def clear_all_history(self) -> None:
        self.memory.clear_all()

    def list_sessions(self) -> list[dict[str, str | int]]:
        return self.memory.list_sessions()

    def run(self, session_id: str, question: str) -> QueryResponse:
        history = self.memory.get(session_id, limit=10)

        if self._wants_dashboard(question):
            dashboard = self.llm.generate_dashboard(question, history)
            response = QueryResponse(
                session_id=session_id,
                question=question,
                generated_sql="-",
                summary=str(dashboard.get("description", "Dashboard generated from previous results.")),
                columns=[],
                rows=[],
                chart=None,
                dashboard=dashboard,
                sources=[],
            )
            self.memory.append(session_id, response.model_dump())
            return response

        search_query = question
        if history:
            search_query = f"{history[-1].get('question', '')} | {question}"
        base_ctx = self.rag.search(search_query, k=20)
        ctx = self._augment_context(question, base_ctx)
        sql = self.llm.generate_sql(question, ctx, history)
        requested_entities = self._extract_entities(question)
        if sql.lstrip().lower().startswith("select") and len(requested_entities) >= 2:
            try:
                expanded_sql = self.llm.expand_sql_dimensions(question, sql, requested_entities, ctx, history)
                if expanded_sql and expanded_sql.lower() != sql.lower():
                    sql = expanded_sql
            except Exception:  # noqa: BLE001
                pass

        try:
            columns, rows = self.db.execute(sql)
        except Exception as exc:  # noqa: BLE001
            repaired_sql = self.llm.repair_sql(question, sql, str(exc), ctx, history)
            if repaired_sql.lower() == sql.lower():
                raise ValueError(f"SQL execution failed: {exc} | generated_sql={sql}") from exc
            try:
                columns, rows = self.db.execute(repaired_sql)
                sql = repaired_sql
            except Exception as exc2:  # noqa: BLE001
                raise ValueError(
                    "SQL execution failed after repair attempt: "
                    f"first_error={exc} | second_error={exc2} | generated_sql={sql} | repaired_sql={repaired_sql}"
                ) from exc2

        # If result shape misses requested entities, rewrite once to force missing dimensions.
        missing_entities = self._missing_entities_in_columns(requested_entities, columns)
        if sql.lstrip().lower().startswith("select") and missing_entities:
            try:
                shape_sql = self.llm.rewrite_sql_for_result_shape(question, sql, missing_entities, ctx, history)
                if shape_sql.lower() != sql.lower():
                    s_columns, s_rows = self.db.execute(shape_sql)
                    still_missing = self._missing_entities_in_columns(requested_entities, s_columns)
                    if s_columns and not still_missing:
                        sql = shape_sql
                        columns, rows = s_columns, s_rows
            except Exception:  # noqa: BLE001
                pass

        # Final strict fallback: force SQL with explicit entity columns.
        missing_entities = self._missing_entities_in_columns(requested_entities, columns)
        if sql.lstrip().lower().startswith("select") and len(requested_entities) >= 2 and missing_entities:
            try:
                forced_sql = self.llm.force_sql_with_entities(question, requested_entities, ctx, history)
                if forced_sql and forced_sql.lower() != sql.lower():
                    f_columns, f_rows = self.db.execute(forced_sql)
                    still_missing = self._missing_entities_in_columns(requested_entities, f_columns)
                    if f_columns and not still_missing:
                        sql = forced_sql
                        columns, rows = f_columns, f_rows
            except Exception:  # noqa: BLE001
                pass

        # If SELECT returned no rows, try one tolerant rewrite pass.
        if sql.lstrip().lower().startswith("select") and len(rows) == 0:
            try:
                rewritten_sql = self.llm.rewrite_sql_for_no_results(question, sql, ctx, history)
                if rewritten_sql.lower() != sql.lower():
                    r_columns, r_rows = self.db.execute(rewritten_sql)
                    if len(r_rows) > 0:
                        sql = rewritten_sql
                        columns, rows = r_columns, r_rows
            except Exception:  # noqa: BLE001
                pass

        want_chart = self._wants_chart(question)
        summary, chart = self.llm.summarize_result(question, sql, rows, want_chart, history)

        response = QueryResponse(
            session_id=session_id,
            question=question,
            generated_sql=sql,
            summary=summary,
            columns=columns,
            rows=rows,
            chart=chart,
            dashboard=None,
            sources=ctx[:6],
        )
        self.memory.append(session_id, response.model_dump())
        return response
