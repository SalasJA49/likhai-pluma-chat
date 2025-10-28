"""
Backend examples demonstrating AnalyticsHandler usage.
This is a minimal adaptation of chatui/analytics/analytics_example.py for Django backend.
"""
from __future__ import annotations

import pandas as pd
from .analytics_handler import AnalyticsHandler


def example_sales_analysis() -> dict:
    data = {
        "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "revenue": [50000, 55000, 60000, 58000, 65000, 70000],
        "expenses": [30000, 32000, 35000, 33000, 36000, 38000],
        "customers": [450, 480, 520, 500, 550, 580],
    }
    handler = AnalyticsHandler()
    results = handler.process_analytics_request(
        data=data,
        user_prompt="show line chart of revenue over month and provide insights",
        params={"focus_areas": ["trends", "growth"]},
    )
    return results


def example_statistical_insights() -> dict:
    import numpy as np
    df = pd.DataFrame({
        "metric": np.random.randn(100) * 10 + 50,
        "category": np.random.choice(["A", "B", "C"], 100),
        "value": np.random.randint(1, 100, 100),
    })
    handler = AnalyticsHandler()
    return handler.process_analytics_request(data=df, user_prompt="analyze metrics")


if __name__ == "__main__":
    out = example_sales_analysis()
    print({k: (v.get('count') if isinstance(v, dict) else type(v)) for k, v in out.items()})
