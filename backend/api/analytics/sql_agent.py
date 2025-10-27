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


class SQLAgent:
    def __init__(self, table_name: str = "data_table"):
        self.table_name = table_name
        self.connection: Optional[sqlite3.Connection] = None

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
            q = self._clean_query(sql_or_prompt)
            if not q or not self._validate_query(q):
                return {"success": False, "error": "Provide a SELECT query that references data_table."}
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
