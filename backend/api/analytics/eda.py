"""
EDA endpoints wiring for Django.
- Accepts file upload (CSV/XLSX) or JSON payload
- Returns chart specs (Plotly JSON) and insights
"""
from __future__ import annotations
from typing import Any, Dict
import io
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .chart_generator import ChartGenerator
from .insight_generator import calculate_statistics, generate_basic_insights, dataframe_from_any
from .sql_agent import SQLAgent


def _df_from_request(request) -> pd.DataFrame:
    # 1) file upload
    f = request.FILES.get("file")
    if f is not None:
        name = (getattr(f, "name", "") or "").lower()
        data = f.read()
        bio = io.BytesIO(data)
        if name.endswith(".csv"):
            return pd.read_csv(bio)
        elif name.endswith(".xlsx") or name.endswith(".xls"):
            return pd.read_excel(bio)
        else:
            # try CSV as default
            try:
                bio.seek(0)
                return pd.read_csv(bio)
            except Exception:
                bio.seek(0)
                return pd.read_excel(bio)

    # 2) JSON body { data: [...] }
    body = request.data or {}
    if isinstance(body, dict) and "data" in body:
        return dataframe_from_any(body["data"])

    raise ValueError("No data provided. Upload a CSV/XLSX file or send JSON {data: ...}.")


@method_decorator(csrf_exempt, name="dispatch")
class EDAProcessAPI(APIView):
    """POST /api/eda/process/
    - form-data: file=<csv/xlsx>
    - or JSON: { data: [...], prompt?: string }
    Returns: { charts: [{figure, type, title, reason}], insights: {...} }
    """
    def post(self, request):
        try:
            df = _df_from_request(request)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    prompt = (request.data.get("prompt") or "").strip()

        # Optional: apply SQL transformation if user provided a SELECT query in prompt
        sql_info: Dict[str, Any] | None = None
        if prompt and prompt.strip().upper().startswith("SELECT"):
            agent = SQLAgent()
            sql_res = agent.execute(df, prompt, assume_sql=True)
            if sql_res.get("success"):
                df = sql_res["data"]
                sql_info = {
                    "query": sql_res["query"],
                    "summary": sql_res["transformation_summary"],
                    "original_shape": sql_res["original_shape"],
                    "result_shape": sql_res["result_shape"],
                }

        # Basic heuristics for charts
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        chart_specs = []
        if categorical_cols and numeric_cols:
            chart_specs.append({"type": "bar", "x": categorical_cols[0], "y": numeric_cols[0], "title": f"{numeric_cols[0]} by {categorical_cols[0]}", "reason": "Comparing values across categories"})
        if len(numeric_cols) >= 2:
            chart_specs.append({"type": "line", "x": df.columns[0], "y": numeric_cols[0], "title": f"{numeric_cols[0]} Trend", "reason": "Showing trend over sequence"})
        if numeric_cols:
            chart_specs.append({"type": "histogram", "x": numeric_cols[0], "title": f"Distribution of {numeric_cols[0]}", "reason": "Understanding distribution"})
        chart_specs = chart_specs[:3]

        cg = ChartGenerator()
        charts = []
        for spec in chart_specs:
            try:
                fig = cg.create_chart(
                    chart_type=spec.get("type", "bar"),
                    data=df,
                    title=spec.get("title"),
                    x=spec.get("x"),
                    y=spec.get("y"),
                )
                charts.append({
                    "figure": fig,
                    "type": spec.get("type"),
                    "title": spec.get("title"),
                    "reason": spec.get("reason", "")
                })
            except Exception:
                continue

        stats = calculate_statistics(df)
        insights = generate_basic_insights(df, stats)
        return Response({
            "charts": {"success": True, "charts": charts, "count": len(charts)},
            "insights": {"success": True, "data": {**insights, "statistics": stats}},
            **({"sql_transformation": sql_info} if sql_info else {}),
        })
