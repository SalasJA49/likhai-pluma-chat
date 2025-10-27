"""
Django-adapted insight generator based on chatui/analytics/insight_generator.py
- Calculates statistics with pandas
- Uses LLM via Foundry later (optional); for now provides deterministic fallback
"""
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np


def calculate_statistics(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    stats: Dict[str, Dict[str, float]] = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        mean_val = float(s.mean()) if pd.notna(s.mean()) else 0.0
        std_val = float(s.std()) if pd.notna(s.std()) else 0.0
        min_val = float(s.min()) if pd.notna(s.min()) else 0.0
        max_val = float(s.max()) if pd.notna(s.max()) else 0.0
        q25 = float(s.quantile(0.25)) if pd.notna(s.quantile(0.25)) else 0.0
        q75 = float(s.quantile(0.75)) if pd.notna(s.quantile(0.75)) else 0.0
        iqr = q75 - q25
        stats[col] = {
            "mean": mean_val,
            "median": float(s.median()) if pd.notna(s.median()) else 0.0,
            "std": std_val,
            "min": min_val,
            "max": max_val,
            "q25": q25,
            "q75": q75,
            "iqr": iqr,
            "range": max_val - min_val,
            "cv": (std_val / abs(mean_val) * 100) if mean_val else 0.0,
            "skewness": float(s.skew()) if len(s) > 2 and pd.notna(s.skew()) else 0.0,
            "count": int(s.count()),
            "missing": int(df[col].isna().sum()),
        }
    return stats


def generate_basic_insights(df: pd.DataFrame, stats: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    return {
        "key_findings": f"Dataset has {df.shape[0]} rows and {df.shape[1]} columns.",
        "insights": [
            "Descriptive statistics computed for numeric columns.",
            "Review distribution metrics to understand spread and skewness.",
        ],
        "recommendations": [
            "Check high CV columns for variability.",
            "Investigate outliers based on IQR bounds.",
        ],
    }


def dataframe_from_any(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict):
        return pd.DataFrame(data)
    if isinstance(data, list):
        return pd.DataFrame(data)
    raise ValueError("Data must be DataFrame, dict, or list")
