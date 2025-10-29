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
from django.conf import settings

from .chart_generator import ChartGenerator
from .insight_generator import calculate_statistics, generate_basic_insights, dataframe_from_any
from .sql_agent import SQLAgent
from .analytics_handler import AnalyticsHandler
try:
    from .services.foundry_service import FoundryService  # type: ignore
except Exception:
    FoundryService = None  # type: ignore


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
        elif name.endswith(".json"):
            # Support JSON dataset uploads: { data: [...] } or array of records
            import json
            bio.seek(0)
            try:
                payload = json.loads(bio.read().decode("utf-8"))
            except Exception as je:
                raise ValueError(f"Invalid JSON file: {je}")
            if isinstance(payload, dict):
                # Guardrail: user might upload a previous EDA response
                if any(k in payload for k in ("charts", "insights", "tables")) and "data" not in payload:
                    raise ValueError(
                        "It looks like you uploaded an EDA results JSON. Please upload a dataset (CSV/XLSX) or a JSON file shaped as { data: [...] }."
                    )
                for key in ("data", "rows", "records", "items", "dataset"):
                    if key in payload:
                        from .insight_generator import dataframe_from_any as _dfa
                        return _dfa(payload[key])
            if isinstance(payload, list):
                from .insight_generator import dataframe_from_any as _dfa
                return _dfa(payload)
            raise ValueError("JSON file did not contain a supported 'data' shape.")
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
    if isinstance(body, dict):
        if "data" in body:
            return dataframe_from_any(body["data"])
        for key in ("rows", "records", "items", "dataset"):
            if key in body:
                return dataframe_from_any(body[key])
        if any(k in body for k in ("charts", "insights", "tables")):
            raise ValueError(
                "Request body looks like an EDA response. Please send a dataset via file upload or JSON with a 'data' array of records."
            )

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
        provider = (request.data.get("provider") or "").strip().lower() or None
        model_deployment = (request.data.get("model_deployment") or request.data.get("deployment") or request.data.get("model") or "").strip() or None
        mode = (request.data.get("mode") or "").strip().lower() or None
        if not provider:
            provider = (getattr(settings, "EDA_DEFAULT_PROVIDER", "") or "").strip().lower() or None

        # Use the richer analytics handler with integrated SQLAgent heuristics
        # This mirrors the chatui flow: the handler decides if/when to apply SQL
        # Optional Foundry wiring
        foundry = None
        if provider == "foundry" and FoundryService is not None:
            try:
                foundry = FoundryService(model_deployment=model_deployment, mode=mode)
            except Exception:
                foundry = None  # fallback if misconfigured
        sql_agent = SQLAgent(foundry=foundry)
        handler = AnalyticsHandler(sql_agent=sql_agent, foundry=foundry)
        results = handler.process_analytics_request(data=df, user_prompt=prompt, params={"provider": provider})

        payload: Dict[str, Any] = {
            "charts": results.get("charts", {"success": False}),
            "insights": results.get("insights", {"success": False}),
            "tables": results.get("tables", {}),
        }
        # Surface chart source for easier debugging/rendering on the client
        if "chart_source" in results:
            payload["chart_source"] = results["chart_source"]
        # If SQL ran inside the handler, it will include sql_transformation metadata
        if "sql_transformation" in results:
            payload["sql_transformation"] = results["sql_transformation"]
        # Only surface SQL warnings when no special aggregation took over
        if "sql_warning" in results and results.get("chart_source") != "aggregation":
            payload["sql_warning"] = results["sql_warning"]
        return Response(payload)
