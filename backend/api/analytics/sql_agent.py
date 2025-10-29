"""
Simplified SQLAgent adapted from chatui/analytics/sql_agent.py for Django.
- Uses in-memory SQLite to transform a pandas DataFrame according to a SQL query
- Can optionally attempt LLM generation later (stubbed out here)
"""
from __future__ import annotations
import sqlite3
import re
from typing import Any, Dict, Optional
import pandas as pd

try:
    # Optional: Foundry service for NL->SQL
    from .services.foundry_service import FoundryService  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    FoundryService = None  # type: ignore


class SQLAgent:
    def __init__(self, table_name: str = "data_table", foundry: Any = None):
        self.table_name = table_name
        self.connection: Optional[sqlite3.Connection] = None
        self.foundry = foundry  # Optional FoundryService instance

    def _create_temp_database(self, df: pd.DataFrame):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = sqlite3.connect(":memory:")
        df.to_sql(self.table_name, self.connection, index=False, if_exists="replace")

    def _close(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

    def _validate_query(self, query: str) -> bool:
        if not query:
            return False
        q = query.strip().rstrip(";")
        if not q.upper().startswith("SELECT"):
            return False
        # Disallow dangerous operations
        forbidden = [
            "DROP ", "DELETE ", "INSERT ", "UPDATE ", "ALTER ", "CREATE ", "TRUNCATE ",
            "ATTACH ", "DETACH ", "PRAGMA ", ";--", "--"  # basic
        ]
        uq = q.upper()
        for k in forbidden:
            if k in uq:
                return False
        # Must reference table name
        if self.table_name not in q:
            return False
        return True

    def _clean_query(self, text: str) -> Optional[str]:
        if not text:
            return None
        q = text.strip()
        if q.startswith("```sql"):
            q = q[6:]
        if q.startswith("```"):
            q = q[3:]
        if q.endswith("```"):
            q = q[:-3]
        q = q.strip()
        # Remove leading labels like "SQL Query:" etc.
        for prefix in ["SQL Query:", "Query:"]:
            if q.lower().startswith(prefix.lower()):
                q = q[len(prefix):].strip()
        if not q.upper().startswith("SELECT"):
            m = re.search(r"(SELECT\s+.*)", q, re.IGNORECASE | re.DOTALL)
            if m:
                q = m.group(1)
        q = q.strip().rstrip(";")
        return q or None

    def execute(self, df: pd.DataFrame, sql_or_prompt: str, assume_sql: bool = False) -> Dict[str, Any]:
        """
        Execute a SQL transformation.
        - If assume_sql=True, treat sql_or_prompt as SQL directly.
        - Otherwise, attempt to use it as SQL first; if it doesn't validate, return warning (no LLM here).
        """
        try:
            self._create_temp_database(df)
            q = self._clean_query(sql_or_prompt) if assume_sql else None
            if not assume_sql:
                # If prompt not explicit SQL, try Foundry to generate SQL if available
                if not q:
                    q = self._maybe_generate_sql_with_foundry(df, sql_or_prompt)
            if not q or not self._validate_query(q):
                return {"success": False, "error": "Provide a SELECT query that references data_table or enable Foundry NL→SQL."}
            result = pd.read_sql_query(q, self.connection)
            return {
                "success": True,
                "data": result,
                "query": q,
                "original_shape": df.shape,
                "result_shape": result.shape,
                "transformation_summary": self._summarize(df, result, q),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self._close()

    # Compatibility wrapper with chatui-style interface
    def process_sql_request(
        self,
        df: pd.DataFrame,
        user_prompt: str,
        context: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        ChatUI compatibility: accept a natural-language prompt but, in this simplified
        backend version, we only accept direct SELECT queries. If the prompt is not a
        valid SELECT, return a warning and continue without transformation.

        Returns the same shape as the chatui SQLAgent on success.
        """
        # If the prompt looks like SQL, execute directly; otherwise attempt NL→SQL via Foundry when configured
        looks_like_sql = bool(self._clean_query(user_prompt)) and user_prompt.strip().upper().startswith("SELECT")
        return self.execute(df, user_prompt, assume_sql=looks_like_sql)

    # --- Foundry NL->SQL helper ---
    def _maybe_generate_sql_with_foundry(self, df: pd.DataFrame, prompt: str) -> Optional[str]:
        if not self.foundry or FoundryService is None:
            return None
        try:
            schema_lines = []
            for col, dtype in df.dtypes.items():
                schema_lines.append(f"- {col}: {str(dtype)}")
            head_preview = df.head(10).to_dict(orient="records")
            system_prompt = (
                "You are a data SQL assistant. Generate a single SQLite SELECT statement over the table 'data_table'.\n"
                "- Only output the SQL. Do not include explanations or code fences.\n"
                "- The table name is data_table. Use only columns that exist.\n"
                "- Use valid SQLite syntax. If aggregation is needed, include GROUP BY.\n"
            )
            user_prompt = (
                f"User request: {prompt}\n\n"
                f"Schema (name: type):\n" + "\n".join(schema_lines) + "\n\n"
                f"Example rows (JSON):\n{head_preview}"
            )
            text = self.foundry.complete(system_prompt + "\n\n" + user_prompt)
            if not text:
                return None
            # Clean the returned text to extract a SELECT
            q = self._clean_query(text)
            # Ensure table name present
            if q and self.table_name not in q:
                # Try to inject table name if missing and FROM clause present without name
                # naive fallback
                q = q.replace("FROM ", f"FROM {self.table_name} ")
            return q
        except Exception:
            return None

    def _summarize(self, original_df: pd.DataFrame, result_df: pd.DataFrame, query: str) -> str:
        parts = []
        o_rows, o_cols = original_df.shape
        r_rows, r_cols = result_df.shape
        if r_rows < o_rows:
            parts.append(f"Filtered from {o_rows} to {r_rows} rows")
        elif r_rows > o_rows:
            parts.append(f"Expanded from {o_rows} to {r_rows} rows")
        else:
            parts.append(f"Maintained {r_rows} rows")
        if r_cols != o_cols:
            parts.append(f"Columns: {r_cols} vs {o_cols}")
        U = query.upper()
        ops = []
        if "WHERE" in U: ops.append("filtering")
        if "GROUP BY" in U: ops.append("aggregation")
        if "ORDER BY" in U: ops.append("sorting")
        if any(k in U for k in ["SUM(", "COUNT(", "AVG(", "MAX(", "MIN("]):
            ops.append("calculation")
        if ops:
            parts.append("Operations: " + ", ".join(ops))
        return " | ".join(parts)
