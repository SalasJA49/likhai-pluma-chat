"""
Insight generation utilities (backend/Django).
- Provides comprehensive statistics and pattern detection similar to chatui version
- No LLM dependency; returns deterministic, useful narratives by default
"""
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)


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


class InsightGenerator:
    """Generate analytics insights: stats, patterns, and narrative text.

    Synchronous version adapted for backend use.
    """

    def generate_insights(
        self,
        data: pd.DataFrame,
        context: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            stats = self._calculate_statistics(data)
            patterns = self._detect_patterns(data)
            narrative = self._narrative_fallback(data, stats, patterns, context, focus_areas)
            return {
                "statistics": stats,
                "patterns": patterns,
                "key_findings": narrative.get("key_findings", ""),
                "insights": narrative.get("insights", []),
                "recommendations": narrative.get("recommendations", []),
            }
        except Exception as e:
            logger.exception("Error generating insights")
            return {"error": str(e)}

    def generate_llm_insights(
        self,
        foundry_service: Any,
        data: pd.DataFrame,
        context: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Use Azure AI Foundry to produce richer insights.

        Returns a dict with keys matching deterministic insights or None on failure.
        """
        try:
            stats = self._calculate_statistics(data)
            patterns = self._detect_patterns(data)

            focus_txt = ", ".join(focus_areas) if focus_areas else ""
            prompt = (
                "You are a senior data analyst. Write concise insights for stakeholders.\n"
                "Return STRICT JSON with keys: key_findings (string), insights (array[string]), recommendations (array[string]).\n"
                "Keep it factual based on the provided stats and patterns, avoid speculation.\n\n"
                f"Context: {context or 'n/a'}\n"
                f"Focus areas: {focus_txt or 'n/a'}\n\n"
                f"Statistics (JSON):\n{json.dumps(stats)}\n\n"
                f"Patterns (JSON):\n{json.dumps(patterns)}\n\n"
                "Output JSON only."
            )
            text = foundry_service.complete(prompt)
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return None
            # Coerce shapes
            return {
                "statistics": stats,
                "patterns": patterns,
                "key_findings": parsed.get("key_findings", ""),
                "insights": parsed.get("insights", []) or [],
                "recommendations": parsed.get("recommendations", []) or [],
            }
        except Exception as e:
            logger.warning("LLM insights generation failed: %s", e)
            return None

    # --- Internal helpers (largely aligned with chatui implementation) ---
    def _calculate_statistics(self, data: pd.DataFrame) -> Dict[str, Any]:
        return calculate_statistics(data)

    def _detect_patterns(self, data: pd.DataFrame) -> Dict[str, Any]:
        patterns: Dict[str, Any] = {"trends": [], "outliers": [], "correlations": []}

        numeric_cols = data.select_dtypes(include=[np.number]).columns
        # Simple trend via slope on index order
        for col in numeric_cols:
            if len(data) > 1:
                x = np.arange(len(data))
                y = data[col].to_numpy(dtype=float)
                mask = ~np.isnan(y)
                if mask.sum() > 1:
                    try:
                        slope = float(np.polyfit(x[mask], y[mask], 1)[0])
                        if np.isfinite(slope):
                            # Scale threshold to std for robustness
                            std_val = float(np.nanstd(y)) if np.isfinite(np.nanstd(y)) else 0.0
                            if std_val and abs(slope) > (std_val * 0.1):
                                patterns["trends"].append(
                                    {
                                        "column": col,
                                        "direction": "increasing" if slope > 0 else "decreasing",
                                        "strength": abs(slope),
                                    }
                                )
                    except Exception:
                        continue

        # Outliers via IQR
        for col in numeric_cols:
            try:
                s = data[col].astype(float)
                q1 = float(s.quantile(0.25))
                q3 = float(s.quantile(0.75))
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                mask = (s < lower) | (s > upper)
                if mask.any():
                    out_vals = s[mask].tolist()
                    patterns["outliers"].append(
                        {"column": col, "count": int(mask.sum()), "values": out_vals[:5]}
                    )
            except Exception:
                continue

        # Correlations
        num_cols = list(numeric_cols)
        if len(num_cols) > 1:
            try:
                corr = data[num_cols].corr(numeric_only=True)
                for i, c1 in enumerate(num_cols):
                    for c2 in num_cols[i + 1 :]:
                        val = float(corr.loc[c1, c2]) if not pd.isna(corr.loc[c1, c2]) else 0.0
                        if abs(val) > 0.5:
                            patterns["correlations"].append(
                                {
                                    "columns": [c1, c2],
                                    "correlation": val,
                                    "strength": "strong" if abs(val) > 0.7 else "moderate",
                                }
                            )
            except Exception:
                pass

        return patterns

    def _narrative_fallback(
        self,
        data: pd.DataFrame,
        stats: Dict[str, Any],
        patterns: Dict[str, Any],
        context: Optional[str],
        focus_areas: Optional[List[str]],
    ) -> Dict[str, Any]:
        # Provide a readable, useful summary without LLMs
        rows, cols = data.shape
        focus_txt = f" Focus: {', '.join(focus_areas)}." if focus_areas else ""
        ctx_txt = f" Context: {context}." if context else ""

        key_findings = (
            f"Analysis complete for {rows} rows and {cols} columns." + ctx_txt + focus_txt
        )

        insights: List[str] = []

        # If time series, report change and extrema with dates
        try:
            # Identify datetime and numeric columns
            dt_cols = [c for c in data.columns if np.issubdtype(data[c].dtype, np.datetime64)]
            if not dt_cols:
                # Try parseable date column
                for c in data.columns:
                    if data[c].dtype == object:
                        parsed = pd.to_datetime(data[c], errors="coerce")
                        if parsed.notna().mean() > 0.8:
                            data = data.copy()
                            data[c] = parsed
                            dt_cols = [c]
                            break
            num_cols = data.select_dtypes(include=[np.number]).columns.tolist()
            if dt_cols and num_cols:
                t, y = dt_cols[0], num_cols[0]
                s = data[[t, y]].dropna().sort_values(by=t)
                if len(s) >= 2:
                    start_date, end_date = s[t].iloc[0], s[t].iloc[-1]
                    start_val, end_val = float(s[y].iloc[0]), float(s[y].iloc[-1])
                    delta = end_val - start_val
                    pct = (delta / start_val * 100.0) if start_val else 0.0
                    insights.append(
                        f"From {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}, {y} changed by {delta:.2f} ({pct:.2f}%)."
                    )
                    # Extrema
                    min_idx = int(s[y].idxmin())
                    max_idx = int(s[y].idxmax())
                    min_val, max_val = float(s[y].min()), float(s[y].max())
                    min_date, max_date = s.loc[min_idx, t], s.loc[max_idx, t]
                    insights.append(
                        f"Minimum {y} {min_val:.2f} on {min_date:%Y-%m-%d}; maximum {max_val:.2f} on {max_date:%Y-%m-%d}."
                    )
                    # Up/down counts
                    deltas = s[y].diff().dropna()
                    up = int((deltas > 0).sum())
                    down = int((deltas < 0).sum())
                    insights.append(f"Up days: {up}, down days: {down} (net {(up-down)}).")
        except Exception:
            pass

        # Mention top spread/variability columns
        try:
            by_cv = [
                (c, s.get("cv", 0.0)) for c, s in stats.items() if isinstance(s, dict)
            ]
            by_cv.sort(key=lambda x: x[1], reverse=True)
            if by_cv[:2]:
                cols_txt = ", ".join([f"{c} (CV {cv:.1f}%)" for c, cv in by_cv[:2]])
                insights.append(f"Highest variability columns: {cols_txt}.")
        except Exception:
            pass

        # Mention trend columns
        for tr in patterns.get("trends", [])[:2]:
            insights.append(
                f"{tr['column']} shows a {tr['direction']} trend (slope {tr['strength']:.3f})."
            )

        # Mention outliers
        for out in patterns.get("outliers", [])[:2]:
            insights.append(
                f"Outliers detected in {out['column']}: {out['count']} potential values beyond IQR bounds."
            )

        # Mention correlations
        for corr in patterns.get("correlations", [])[:2]:
            c1, c2 = corr["columns"]
            strength = corr["strength"]
            val = corr["correlation"]
            insights.append(f"{c1} and {c2} show {strength} correlation (r={val:.2f}).")

        recommendations = [
            "Investigate high-CV columns for instability or seasonality.",
            "Review outliers to determine if they are data errors or true extremes.",
            "Consider de-trending or segmenting by time if strong trends are present.",
        ]

        return {
            "key_findings": key_findings,
            "insights": insights or [
                "Descriptive statistics computed; review CV and skewness for distribution shape."
            ],
            "recommendations": recommendations,
        }

