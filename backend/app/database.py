from __future__ import annotations

import sqlparse
from mysql.connector import pooling

from app.config import settings


FORBIDDEN_TOKENS = {"drop", "truncate", "alter", "grant", "revoke", "create user"}


class DatabaseClient:
    def __init__(self) -> None:
        self.pool = pooling.MySQLConnectionPool(
            pool_name="assistant_pool",
            pool_size=8,
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
        )

    def _validate_sql(self, sql: str) -> str:
        cleaned = sql.strip().rstrip(";")
        lowered = cleaned.lower()
        if not cleaned:
            raise ValueError("Empty SQL generated")
        if any(token in lowered for token in FORBIDDEN_TOKENS):
            raise ValueError("Blocked potentially destructive SQL")
        statements = [s for s in sqlparse.split(cleaned) if s.strip()]
        if len(statements) != 1:
            raise ValueError("Only a single SQL statement is allowed")
        return statements[0]

    def execute(self, sql: str) -> tuple[list[str], list[dict]]:
        safe_sql = self._validate_sql(sql)
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(safe_sql)
            is_select = safe_sql.lstrip().lower().startswith("select")
            if is_select:
                raw_rows = cursor.fetchall()
                base_columns = [d[0] for d in cursor.description] if cursor.description else []
                seen: dict[str, int] = {}
                columns: list[str] = []
                for col in base_columns:
                    count = seen.get(col, 0) + 1
                    seen[col] = count
                    columns.append(col if count == 1 else f"{col}_{count}")

                rows: list[dict] = []
                for tup in raw_rows:
                    row: dict = {}
                    for i, col in enumerate(columns):
                        row[col] = tup[i] if i < len(tup) else None
                    rows.append(row)
                return columns, rows
            conn.commit()
            return ["status", "affected_rows"], [{"status": "ok", "affected_rows": cursor.rowcount}]
        finally:
            cursor.close()
            conn.close()

    def load_schema_docs(self) -> list[str]:
        column_query = """
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        fk_query = """
        SELECT
            kcu.TABLE_NAME,
            kcu.COLUMN_NAME,
            kcu.REFERENCED_TABLE_NAME,
            kcu.REFERENCED_COLUMN_NAME,
            rc.UPDATE_RULE,
            rc.DELETE_RULE
        FROM information_schema.KEY_COLUMN_USAGE kcu
        LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
            ON rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
            AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        WHERE kcu.TABLE_SCHEMA = %s
          AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY kcu.TABLE_NAME, kcu.COLUMN_NAME
        """

        conn = self.pool.get_connection()
        docs: list[str] = []
        try:
            cursor = conn.cursor()
            cursor.execute(column_query, (settings.MYSQL_DATABASE,))
            for table, column, col_type, is_nullable, col_key in cursor.fetchall():
                key = col_key if col_key else "-"
                nullable = "yes" if str(is_nullable).upper() == "YES" else "no"
                docs.append(
                    f"schema table={table} column={column} type={col_type} key={key} nullable={nullable}"
                )

            cursor.execute(fk_query, (settings.MYSQL_DATABASE,))
            for table, column, ref_table, ref_column, update_rule, delete_rule in cursor.fetchall():
                docs.append(
                    "relationship "
                    f"from={table}.{column} to={ref_table}.{ref_column} "
                    f"join_hint={table}.{column}={ref_table}.{ref_column} "
                    f"on_update={update_rule or '-'} on_delete={delete_rule or '-'}"
                )
            return docs
        finally:
            cursor.close()
            conn.close()
