"""
Django-adapted chart generator based on chatui/analytics/chart_generator.py
- Uses plotly to produce figure JSON suitable for frontend rendering via plotly.js
"""
from typing import Any, Dict, Optional
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
    # Return a serializable Plotly figure spec
    return fig.to_plotly_json()


class ChartGenerator:
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
        if ctype == "line":
            fig = px.line(df, x=x or df.columns[0], y=y or df.columns[1], **kwargs)
        elif ctype == "bar":
            fig = px.bar(df, x=x or df.columns[0], y=y or df.columns[1], **kwargs)
        elif ctype == "scatter":
            fig = px.scatter(df, x=x or df.columns[0], y=y or df.columns[1], **kwargs)
        elif ctype == "pie":
            names = kwargs.pop("names", x if x in df.columns else df.columns[0])
            values = kwargs.pop("values", y if y in df.columns else df.columns[1])
            fig = px.pie(df, names=names, values=values, **kwargs)
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
        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label, template="plotly_white")
        return figure_to_json(fig)
