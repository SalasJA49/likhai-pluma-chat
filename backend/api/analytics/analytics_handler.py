# analytics/analytics_handler.py

"""
Backend analytics handler (Django-safe)
- Integrates SQL intent detection and optional SQLAgent transform (from old Chainlit version)
- Removes Chainlit/UI concerns and any async/await
- Keeps deterministic chart recs + explicit chart parsing
- Produces Plotly figure JSON via ChartGenerator
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
import logging
import numpy as np
import pandas as pd

from .chart_generator import ChartGenerator
from .insight_generator import InsightGenerator

try:
    from .services.foundry_service import FoundryService  # type: ignore
except Exception:  # optional
    FoundryService = None  # type: ignore

logger = logging.getLogger(__name__)


class AnalyticsHandler:
    """
    Main handler for analytics features (backend/Django).

    Usage notes:
    - If you want SQL transforms from NL prompts, inject an SQLAgent instance
      that implements: process_sql_request(df, user_prompt, context) -> dict
        Expected return on success:
          {
            "success": True,
            "data": <pd.DataFrame>,
            "query": "...",
            "transformation_summary": "...",
            "original_shape": (r, c),
            "result_shape": (r2, c2)
          }
    - If no SQLAgent is provided (default), handler falls back to deterministic logic only.
    """

    def __init__(self, sql_agent: Optional[Any] = None, foundry: Any = None):
        self.chart_gen = ChartGenerator()
        self.insight_gen = InsightGenerator()
        self.sql_agent = sql_agent  # Optional
        self.foundry = foundry  # Optional FoundryService instance

    # ---------------------------- Public entrypoint ----------------------------
    def process_analytics_request(
        self,
        data: Any,
        user_prompt: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process analytics request to produce charts and insights.

        Args:
            data: DataFrame, dict/list (records), or JSON/file path string
            user_prompt: natural-language description of desired analysis/visuals
            params: Optional processing params (e.g., {"focus_areas": [...]})

        Returns:
            Dict with:
              - charts: { success, charts: [{figure, type, title, reason}], count }
              - insights: { success, data | error }
              - processed: { shape, columns }
              - (optional) sql_transformation / sql_warning
              - chart_source: "explicit" | "default"
        """
        params = params or {}
        try:
            df = self._prepare_data(data)
            if df is None or df.empty:
                return {"error": "No valid data provided"}

            results: Dict[str, Any] = {}

            # 0) Optional SQL transformation if prompt implies it AND sql_agent exists
            if self._check_sql_needed(user_prompt) and self.sql_agent is not None:
                try:
                    sql_result = self.sql_agent.process_sql_request(
                        df=df,
                        user_prompt=user_prompt,
                        context={"original_request": user_prompt},
                    )
                    if sql_result and sql_result.get("success"):
                        df = sql_result["data"]
                        results["sql_transformation"] = {
                            "query": sql_result.get("query"),
                            "summary": sql_result.get("transformation_summary"),
                            "original_shape": sql_result.get("original_shape"),
                            "result_shape": sql_result.get("result_shape"),
                        }
                        logger.info("SQL transformation applied.")
                    else:
                        results["sql_warning"] = (sql_result or {}).get(
                            "error", "SQL transformation failed"
                        )
                        logger.warning("SQL transformation failed; continuing with original data.")
                except Exception as se:
                    results["sql_warning"] = f"SQL transformation error: {se}"
                    logger.warning("SQL transformation error; continuing with original data.")

            provider = (params or {}).get("provider")
            # 1) Explicit chart requests from the prompt
            explicit_charts = self._extract_explicit_chart_requests(user_prompt, df)
            picked_charts: List[Dict[str, Any]] = []
            if explicit_charts:
                picked_charts = explicit_charts
                results["chart_source"] = "explicit"
            else:
                # 1b) LLM-driven recs if enabled
                llm_specs = self._try_llm_chart_recommendations(df, user_prompt, provider)
                if llm_specs:
                    picked_charts = llm_specs
                    results["chart_source"] = "llm"
                else:
                    # 2) Deterministic default charts (no LLM)
                    picked_charts = self._get_default_charts(df)
                    results["chart_source"] = "default"

            # 2.5) Semantic aggregations for common asks (e.g., "top 10 customers by purchases")
            agg_payload = self._maybe_apply_common_aggregation(df, user_prompt)
            if agg_payload is not None:
                # Replace df with aggregated view for downstream visuals specific to this task
                df_agg = agg_payload["data"]
                # Enrich chart list with bar + pie + scatter for the top-N summary
                top_title = agg_payload.get("title") or "Top N Summary"
                cust_col = agg_payload.get("group_col")
                val_col = agg_payload.get("value_col")
                qty_col = agg_payload.get("qty_col")
                extra_specs: List[Dict[str, Any]] = [
                    {"type": "bar", "x": cust_col, "y": val_col, "title": f"{val_col} by {cust_col}", "reason": "Top-N ranking"},
                    {"type": "pie", "names": cust_col, "values": val_col, "title": f"Share of {val_col} by {cust_col}", "reason": "Proportion across top-N"},
                ]
                if qty_col and qty_col in df_agg.columns:
                    extra_specs.append({
                        "type": "scatter", "x": val_col, "y": qty_col,
                        "title": f"{qty_col} vs {val_col} (Top {agg_payload.get('top_n')})",
                        "reason": "Relationship between spend and quantity",
                    })
                charts_result = self._generate_multiple_charts(df_agg, extra_specs)
                results["charts"] = charts_result
                results["chart_source"] = "aggregation"
                # Tables: top-N records and statistics on totals
                from .insight_generator import calculate_statistics
                stats = calculate_statistics(df_agg.select_dtypes(include=["number"]))
                results["tables"] = {
                    "top_n": {
                        "title": top_title,
                        "columns": df_agg.columns.tolist(),
                        "rows": df_agg.to_dict(orient="records"),
                        "note": agg_payload.get("note", ""),
                    },
                    "statistics": stats,
                }
            else:
                charts_result = self._generate_multiple_charts(df, picked_charts)
                results["charts"] = charts_result

            # 3) Insights (stats + narrative fallback)
            insights_result = self._generate_insights(df, user_prompt, params)
            results["insights"] = insights_result
            # If we already attached tables via special aggregation, keep; otherwise expose stats for UI table
            if "tables" not in results and isinstance(results.get("insights"), dict):
                data = results["insights"].get("data") or {}
                if isinstance(data, dict) and data.get("statistics"):
                    results["tables"] = {"statistics": data["statistics"]}

            # 4) Debug/trace metadata
            results["processed"] = {"shape": df.shape, "columns": df.columns.tolist()}
            return results

        except Exception as e:
            logger.exception("Error processing analytics request")
            return {"error": str(e)}

    # -------------------------- Special-case aggregations --------------------------
    def _maybe_apply_common_aggregation(self, df: pd.DataFrame, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Detect very common analytics intents and compute them directly without requiring SQL/LLM.
        Currently supports:
          - "total purchases/sales per customer ... top N"

        Returns a payload with aggregated DataFrame and metadata, or None if no match.
        """
        if not user_prompt or df is None or df.empty:
            return None

        p = user_prompt.lower()
        # columns heuristics (expanded synonyms)
        cols = {c.lower(): c for c in df.columns}
        customer_col = (
            cols.get("customer")
            or cols.get("customer_id")
            or cols.get("customername")
            or cols.get("customer_name")
            or cols.get("client")
            or cols.get("client_id")
            or cols.get("buyer")
            or cols.get("buyer_id")
        )
        # value column: sales/purchases/amount/revenue/spend/value
        value_candidates = [
            "sales",
            "purchases",
            "amount",
            "revenue",
            "spend",
            "value",
            "total_sales",
            "total_purchases",
            "purchase_total",
            "sales_amount",
        ]
        value_col = None
        for key in value_candidates:
            if key in cols:
                value_col = cols[key]
                break
        qty_col = cols.get("quantity") or cols.get("qty") or cols.get("units") or cols.get("count")

        # detect intent phrases
        mentions_total = any(k in p for k in ["total", "sum", "aggregate"]) and any(
            k in p for k in ["purchase", "purchases", "sales", "spend", "amount"]
        )
        mentions_customer = any(k in p for k in ["customer", "client", "buyer"])
        # extract top N
        import re
        m = re.search(r"top\s+(\d{1,3})", p)
        # Default to Top 10 when not specified; be explicit only when a number is present
        top_n = int(m.group(1)) if m else 10

        if customer_col and value_col and mentions_total and mentions_customer:
            try:
                g = df.groupby(customer_col, dropna=False)
                agg_dict = {value_col: "sum"}
                if qty_col and qty_col in df.columns:
                    agg_dict[qty_col] = "sum"
                out = g.agg(agg_dict).reset_index()
                # rename totals for clarity
                rename_map = {}
                if value_col in out.columns and value_col.lower() != "total":
                    rename_map[value_col] = f"total_{value_col}"
                if qty_col and qty_col in out.columns and qty_col.lower() != "total_quantity":
                    rename_map[qty_col] = f"total_{qty_col}"
                if rename_map:
                    out = out.rename(columns=rename_map)
                # sort by value desc
                val_col_final = rename_map.get(value_col, value_col)
                out = out.sort_values(by=val_col_final, ascending=False).head(top_n)
                plural = customer_col if top_n == 1 else f"{customer_col}s"
                title = f"Top {top_n} {plural} by {val_col_final}"
                return {
                    "data": out,
                    "group_col": customer_col,
                    "value_col": val_col_final,
                    "qty_col": rename_map.get(qty_col, qty_col),
                    "top_n": top_n,
                    "title": title,
                    "note": "Computed directly by backend heuristic (no SQL required)",
                }
            except Exception:
                return None

        return None

    # ------------------------------ SQL intent ---------------------------------
    def _check_sql_needed(self, user_prompt: str) -> bool:
        """
        Heuristic to determine if a SQL-like transform is implied by the prompt.
        Mirrors the old Chainlit logic but sync + logger only.
        """
        if not user_prompt:
            return False

        prompt_lower = user_prompt.lower()

        sql_keywords = [
            # Filtering
            "filter", "where", "only", "exclude", "select",
            "specific", "particular", "certain",
            # Aggregation
            "sum", "total", "average", "mean", "count",
            "group by", "grouped", "aggregate", "aggregated",
            "per", "by category", "by type", "by group",
            # Date/Time filtering
            "year", "month", "date", "period", "between",
            "since", "until", "before", "after", "during",
            # Sorting/Limiting
            "top", "bottom", "highest", "lowest", "first",
            "last", "sort", "order", "rank",
            # Calculations
            "calculate", "compute", "derive", "maximum",
            "minimum", "median", "percentile",
        ]

        if any(k in prompt_lower for k in sql_keywords):
            logger.info("SQL intent detected from keywords.")
            return True

        # Year patterns like 2023, 1999, etc.
        import re
        if re.search(r"\b(19|20)\d{2}\b", user_prompt):
            logger.info("Year pattern detected; likely a filter -> SQL needed.")
            return True

        return False

    # ---------------------------- Charting helpers ----------------------------
    def _extract_explicit_chart_requests(
        self, user_prompt: str, df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        if not user_prompt:
            return []

        prompt_lower = user_prompt.lower()
        explicit_charts: List[Dict[str, Any]] = []

        chart_patterns: Dict[str, List[str]] = {
            "line": ["line chart", "line graph", "trend line", "time series"],
            "bar": ["bar chart", "bar graph", "column chart", "vertical bar"],
            "scatter": ["scatter plot", "scatter chart", "scatterplot", "point plot"],
            "pie": ["pie chart", "pie graph", "donut chart"],
            "histogram": ["histogram", "distribution chart", "frequency chart"],
            "box": ["box plot", "boxplot", "box and whisker"],
            "heatmap": ["heatmap", "heat map", "correlation matrix"],
            "area": ["area chart", "area graph", "filled line"],
            "funnel": ["funnel chart", "funnel graph"],
            "waterfall": ["waterfall chart", "waterfall graph"],
        }

        requested_types: List[str] = [
            ctype for ctype, pats in chart_patterns.items() if any(p in prompt_lower for p in pats)
        ]
        requested_types = list(dict.fromkeys(requested_types))  # dedupe keep order
        if not requested_types:
            return []

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        mentioned_columns = [col for col in df.columns if col.lower() in prompt_lower]

        specs: List[Dict[str, Any]] = []
        for chart_type in requested_types:
            spec = self._build_chart_spec_from_prompt(
                chart_type, df, user_prompt, numeric_cols, categorical_cols, mentioned_columns
            )
            if spec:
                specs.append(spec)
        return specs

    def _build_chart_spec_from_prompt(
        self,
        chart_type: str,
        df: pd.DataFrame,
        prompt: str,
        numeric_cols: List[str],
        categorical_cols: List[str],
        mentioned_columns: List[str],
    ) -> Optional[Dict[str, Any]]:
        spec: Dict[str, Any] = {
            "type": chart_type,
            "title": f"{chart_type.capitalize()} Chart",
            "reason": f"User explicitly requested {chart_type} chart",
        }

        if chart_type in ["line", "bar", "scatter", "area"]:
            if len(mentioned_columns) >= 2:
                spec["x"], spec["y"] = mentioned_columns[0], mentioned_columns[1]
            elif len(mentioned_columns) == 1 and mentioned_columns[0] in numeric_cols:
                spec["x"], spec["y"] = df.columns[0], mentioned_columns[0]
            elif categorical_cols and numeric_cols:
                spec["x"], spec["y"] = categorical_cols[0], numeric_cols[0]
            else:
                spec["x"] = df.columns[0] if len(df.columns) > 0 else None
                spec["y"] = df.columns[1] if len(df.columns) > 1 else None

        elif chart_type == "pie":
            if len(mentioned_columns) >= 2:
                spec["names"], spec["values"] = mentioned_columns[0], mentioned_columns[1]
            elif categorical_cols and numeric_cols:
                spec["names"], spec["values"] = categorical_cols[0], numeric_cols[0]
            else:
                spec["names"] = df.columns[0] if len(df.columns) > 0 else None
                spec["values"] = df.columns[1] if len(df.columns) > 1 else None

        elif chart_type == "histogram":
            if mentioned_columns and mentioned_columns[0] in numeric_cols:
                spec["x"] = mentioned_columns[0]
            elif numeric_cols:
                spec["x"] = numeric_cols[0]
            else:
                spec["x"] = df.columns[0] if len(df.columns) > 0 else None

        elif chart_type == "box":
            if len(mentioned_columns) >= 1 and mentioned_columns[0] in numeric_cols:
                spec["y"] = mentioned_columns[0]
                if len(categorical_cols) > 0:
                    spec["x"] = categorical_cols[0]
            elif numeric_cols:
                spec["y"] = numeric_cols[0]
                if categorical_cols:
                    spec["x"] = categorical_cols[0]

        # Title refinement
        if spec.get("x") and spec.get("y"):
            spec["title"] = f"{spec['y']} by {spec['x']}"
        elif spec.get("y"):
            spec["title"] = f"Distribution of {spec['y']}"
        elif spec.get("x"):
            spec["title"] = f"Analysis of {spec['x']}"

        return spec if (spec.get("x") or spec.get("y") or spec.get("names")) else None

    def _get_default_charts(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        charts: List[Dict[str, Any]] = []
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        datetime_cols = self._detect_datetime_columns(df)

        # Time series: core line + moving average overlay
        if datetime_cols and numeric_cols:
            tcol, ycol = datetime_cols[0], numeric_cols[0]
            charts.append(
                {
                    "type": "line",
                    "x": tcol,
                    "y": ycol,
                    "title": f"{ycol} over time",
                    "reason": "Time series trend across the date axis",
                }
            )
            try:
                sdf = df[[tcol, ycol]].copy()
                if not np.issubdtype(sdf[tcol].dtype, np.datetime64):
                    sdf[tcol] = pd.to_datetime(sdf[tcol], errors="coerce")
                sdf = sdf.dropna(subset=[tcol]).sort_values(by=tcol)
                sdf["MA_30"] = sdf[ycol].rolling(window=30, min_periods=5).mean()
                charts.append(
                    {
                        "type": "multi_line",
                        "data": {
                            "x": self._to_list_safe(sdf[tcol]),
                            ycol: self._to_list_safe(sdf[ycol]),
                            "MA_30": self._to_list_safe(sdf["MA_30"]),
                        },
                        "series_names": [ycol, "MA_30"],
                        "title": f"{ycol} vs 30-day moving average",
                        "reason": "Smoothed trend helps see medium-term movement",
                    }
                )
            except Exception:
                pass

        # Category vs numeric bar
        if categorical_cols and numeric_cols:
            charts.append(
                {
                    "type": "bar",
                    "x": categorical_cols[0],
                    "y": numeric_cols[0],
                    "title": f"{numeric_cols[0]} by {categorical_cols[0]}",
                    "reason": "Comparing values across categories",
                }
            )

        # Distribution of value
        if numeric_cols:
            ycol = numeric_cols[0]
            charts.append(
                {
                    "type": "histogram",
                    "x": ycol,
                    "title": f"Distribution of {ycol}",
                    "reason": "Understanding value distribution",
                }
            )

            # Distribution of daily change if we have time
            if datetime_cols:
                try:
                    sdf = df[[datetime_cols[0], ycol]].copy()
                    if not np.issubdtype(sdf[datetime_cols[0]].dtype, np.datetime64):
                        sdf[datetime_cols[0]] = pd.to_datetime(sdf[datetime_cols[0]], errors="coerce")
                    sdf = sdf.dropna().sort_values(by=datetime_cols[0])
                    sdf["delta"] = sdf[ycol].diff()
                    charts.append(
                        {
                            "type": "histogram",
                            "data": sdf[["delta"]].dropna(),
                            "x": "delta",
                            "title": f"Distribution of daily change in {ycol}",
                            "reason": "Volatility signature via changes",
                        }
                    )
                except Exception:
                    pass

        return charts[:5]

    def _generate_multiple_charts(
        self, df: pd.DataFrame, chart_specs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        try:
            generated: List[Dict[str, Any]] = []
            for spec in chart_specs:
                try:
                    if spec.get("type") == "multi_line":
                        fig = self.chart_gen.create_multi_series_chart(
                            chart_type="line",
                            data=spec.get("data") or {},
                            series_names=spec.get("series_names", []),
                            title=spec.get("title"),
                        )
                    else:
                        fig = self.chart_gen.create_chart(
                            chart_type=spec.get("type", "bar"),
                            data=spec.get("data", df),
                            title=spec.get("title", "Data Visualization"),
                            x=spec.get("x"),
                            y=spec.get("y"),
                            x_label=spec.get("x_label"),
                            y_label=spec.get("y_label"),
                            names=spec.get("names"),
                            values=spec.get("values"),
                        )
                    generated.append(
                        {
                            "figure": fig,
                            "type": spec.get("type"),
                            "title": spec.get("title"),
                            "reason": spec.get("reason", ""),
                        }
                    )
                except Exception as chart_error:
                    logger.warning("Chart generation failed: %s", chart_error)
                    continue
            return {"success": True, "charts": generated, "count": len(generated)}
        except Exception as e:
            logger.exception("Error generating charts")
            return {"success": False, "error": str(e)}

    # ----------------------------- Insights helpers ----------------------------
    def _generate_insights(
        self, df: pd.DataFrame, user_prompt: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            provider = (params or {}).get("provider")
            context = f"User request: {user_prompt}" if user_prompt else None
            focus_areas = params.get("focus_areas") if params else None
            if provider == "foundry" and self.foundry is not None and FoundryService is not None:
                # Try LLM insights first
                try:
                    llm_insights = self.insight_gen.generate_llm_insights(self.foundry, df, context, focus_areas)
                    if llm_insights:
                        return {"success": True, "data": llm_insights, "source": "llm"}
                except Exception as le:
                    logger.warning("LLM insights failed: %s", le)
            # Fallback deterministic
            insights = self.insight_gen.generate_insights(data=df, context=context, focus_areas=focus_areas)
            return {"success": True, "data": insights, "source": "deterministic"}
        except Exception as e:
            logger.exception("Error generating insights")
            return {"success": False, "error": str(e)}

    # ---------------------------- LLM chart recs -----------------------------
    def _try_llm_chart_recommendations(self, df: pd.DataFrame, user_prompt: str, provider: Optional[str]) -> List[Dict[str, Any]]:
        if provider != "foundry" or self.foundry is None or FoundryService is None:
            return []
        try:
            # Summarize schema and sample
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
            dt_cols = self._detect_datetime_columns(df)
            head_preview = df.head(10).to_dict(orient="records")
            schema_lines = [f"- {c}: {str(df[c].dtype)}" for c in df.columns]
            prompt = (
                "You are a data viz assistant. Propose 2-4 relevant charts for the user's request.\n"
                "Return STRICT JSON array of objects with keys: type, title, reason, and one of:\n"
                "- (x,y) for line/bar/scatter/area\n- (names,values) for pie\n- optional x_label,y_label.\n"
                "Allowed types: line, bar, scatter, area, pie, histogram, box, heatmap.\n"
                "Prefer time-series line when a datetime axis exists.\n"
                f"User request: {user_prompt}\n\n"
                f"Schema (name: type):\n" + "\n".join(schema_lines) + "\n\n"
                f"Detected datetime cols: {dt_cols}\n"
                f"Numeric cols: {numeric_cols}\n"
                f"Categorical cols: {categorical_cols}\n\n"
                f"Sample rows (JSON):\n{head_preview}\n\n"
                "Output: JSON only, no extra text."
            )
            text = self.foundry.complete(prompt)
            import json as _json
            specs = _json.loads(text)
            if not isinstance(specs, list):
                return []
            # Basic validation
            out: List[Dict[str, Any]] = []
            for s in specs:
                if not isinstance(s, dict):
                    continue
                ctype = s.get("type")
                if ctype not in {"line", "bar", "scatter", "area", "pie", "histogram", "box", "heatmap"}:
                    continue
                out.append({
                    "type": ctype,
                    "x": s.get("x"),
                    "y": s.get("y"),
                    "names": s.get("names"),
                    "values": s.get("values"),
                    "title": s.get("title") or f"{ctype.capitalize()} Chart",
                    "reason": s.get("reason") or "LLM recommendation",
                })
            return out[:4]
        except Exception as e:
            logger.warning("LLM chart recommendation failed: %s", e)
            return []

    # ------------------------------- Data helpers -------------------------------
    def _prepare_data(self, data: Any) -> Optional[pd.DataFrame]:
        try:
            if isinstance(data, pd.DataFrame):
                return data
            if isinstance(data, dict):
                return pd.DataFrame(data)
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, str):
                # JSON first
                try:
                    parsed = json.loads(data)
                    return pd.DataFrame(parsed)
                except Exception:
                    pass
                # Files
                if data.endswith(".csv"):
                    return pd.read_csv(data)
                if data.endswith(".xlsx") or data.endswith(".xls"):
                    return pd.read_excel(data)
            return None
        except Exception as e:
            logger.warning("Error preparing data: %s", e)
            return None

    def _detect_datetime_columns(self, df: pd.DataFrame) -> List[str]:
        dt_cols = [c for c in df.columns if np.issubdtype(df[c].dtype, np.datetime64)]
        if dt_cols:
            return dt_cols
        candidates: List[str] = []
        for c in df.columns:
            s = df[c]
            if s.dtype == object or isinstance(s.dtype, pd.CategoricalDtype):
                sample = s.dropna().astype(str).head(25)
                if not len(sample):
                    continue
                parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().mean() >= 0.8:
                    candidates.append(c)
        return candidates

    def _to_list_safe(self, series: pd.Series) -> List[Any]:
        out: List[Any] = []
        for v in series.tolist():
            if isinstance(v, pd.Timestamp):
                out.append(v)  # let your serializer handle ISO conversion
                continue
            try:
                if v is None:
                    out.append(None)
                elif isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                    out.append(None)
                elif isinstance(v, (np.floating, np.integer)):
                    out.append(v.item())
                else:
                    out.append(v)
            except Exception:
                out.append(None)
        return out


# Convenience instance if you want a module-level singleton
analytics_handler = AnalyticsHandler()
