"""
Chart generation utilities (backend/Django) inspired by chatui version.
- Returns Plotly figure as JSON for frontend rendering.
"""
from typing import Any, Dict, Optional, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _prepare_dataframe(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict):
        return pd.DataFrame(data)
    if isinstance(data, list):
        return pd.DataFrame(data)
    raise ValueError("Data must be DataFrame, dict, or list")


def figure_to_json(fig: go.Figure) -> Dict[str, Any]:
    """Return a JSON-safe Plotly figure spec (NaN/Inf -> null).

    Django's JSON renderer rejects NaN/Inf. Plotly figures may contain them
    (e.g., rolling means, diffs). We recursively replace non-finite floats
    with None to keep responses JSON-compliant.
    """
    import math

    def _san(o: Any):
        if isinstance(o, float):
            return None if not math.isfinite(o) else o
        if isinstance(o, (int, str)) or o is None:
            return o
        if isinstance(o, list):
            return [_san(v) for v in o]
        if isinstance(o, dict):
            return {k: _san(v) for k, v in o.items()}
        # Plotly may use numpy types; try converting
        try:
            from numpy import float_, integer
            if isinstance(o, (float_, integer)):
                v = o.item()
                return None if isinstance(v, float) and not math.isfinite(v) else v
        except Exception:
            pass
        return o

    return _san(fig.to_plotly_json())


class ChartGenerator:
    SUPPORTED_CHART_TYPES = [
        "line",
        "bar",
        "scatter",
        "pie",
        "histogram",
        "box",
        "heatmap",
        "area",
        "funnel",
        "waterfall",
    ]

    def __init__(self) -> None:
        self.default_layout = {
            "template": "plotly_white",
            "font": {"family": "Arial, sans-serif", "size": 12},
            "margin": {"l": 50, "r": 50, "t": 50, "b": 50},
        }

    def create_chart(
        self,
        chart_type: str,
        data: Any,
        title: Optional[str] = None,
        x: Optional[str] = None,
        y: Optional[str] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        df = _prepare_dataframe(data)
        ctype = chart_type.lower()
        if ctype not in self.SUPPORTED_CHART_TYPES:
            raise ValueError(f"Unsupported chart type: {chart_type}")

        # absorb generic names/values so non-pie charts don't receive them
        names_kw = kwargs.pop("names", None)
        values_kw = kwargs.pop("values", None)

        if ctype == "line":
            fig = px.line(df, x=x or df.columns[0], y=y or df.columns[1], **kwargs)
        elif ctype == "bar":
            orientation = kwargs.pop("orientation", "v")
            fig = px.bar(df, x=x or df.columns[0], y=y or df.columns[1], orientation=orientation, **kwargs)
        elif ctype == "scatter":
            fig = px.scatter(df, x=x or df.columns[0], y=y or df.columns[1], **kwargs)
        elif ctype == "pie":
            # Map generic x/y into names/values if provided
            names = names_kw if names_kw is not None else (x if isinstance(x, str) and x in df.columns else None)
            values = values_kw if values_kw is not None else (y if isinstance(y, str) and y in df.columns else None)
            if names is None:
                names = df.columns[0]
            if values is None:
                values = df.columns[1]
            if not pd.api.types.is_numeric_dtype(df[values]):
                df = df.copy()
                df[values] = pd.to_numeric(df[values], errors="coerce")
            fig = px.pie(df, names=names, values=values, **{k: v for k, v in kwargs.items()})
        elif ctype == "histogram":
            fig = px.histogram(df, x=x or df.columns[0], **kwargs)
        elif ctype == "box":
            fig = px.box(df, x=x, y=y or df.columns[0], **kwargs)
        elif ctype == "heatmap":
            fig = px.imshow(df, **kwargs)
        elif ctype == "area":
            fig = px.area(df, x=x or df.columns[0], y=y or df.columns[1], **kwargs)
        elif ctype == "funnel":
            fig = px.funnel(df, x=x or df.columns[1], y=y or df.columns[0], **kwargs)
        elif ctype == "waterfall":
            fig = go.Figure(go.Waterfall(x=df[x or df.columns[0]], y=df[y or df.columns[1]]))

        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label, **self.default_layout)
        return figure_to_json(fig)

    def create_multi_series_chart(
        self,
        chart_type: str,
        data: Dict[str, List[Any]],
        series_names: List[str],
        title: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create multi-series line/bar/area chart and return JSON figure."""
        fig = go.Figure()
        x_values = data.get("x", [])
        for series_name in series_names:
            y_values = data.get(series_name, [])
            if chart_type == "line":
                fig.add_trace(go.Scatter(x=x_values, y=y_values, mode="lines", name=series_name))
            elif chart_type == "bar":
                fig.add_trace(go.Bar(x=x_values, y=y_values, name=series_name))
            elif chart_type == "area":
                fig.add_trace(go.Scatter(x=x_values, y=y_values, fill="tozeroy", name=series_name))
        fig.update_layout(title=title, **self.default_layout)
        return figure_to_json(fig)
