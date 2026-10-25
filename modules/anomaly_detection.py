"""
anomaly_detection.py - Statistical + ML-based unusual expense detection.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

MIN_ROWS_FOR_ML = 20  # Minimum transactions to use Isolation Forest
ZSCORE_THRESHOLD = 2.5
IQR_FENCE_MULTIPLIER = 2.0


def _zscore_flags(series: pd.Series, threshold: float = ZSCORE_THRESHOLD) -> pd.Series:
    """Return boolean Series: True where |z-score| > threshold."""
    if series.std() == 0:
        return pd.Series(False, index=series.index)
    z = (series - series.mean()) / series.std()
    return z.abs() > threshold


def statistical_anomaly_detection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rule-based anomaly detection using z-score and IQR methods.
    Returns DataFrame with flag columns added.
    """
    if df.empty:
        return df.copy()

    result = df.copy()
    result["_stat_anomaly"] = False
    result["_stat_reason"] = ""

    # Global amount anomaly
    global_flag = _zscore_flags(result["amount"])
    result.loc[global_flag, "_stat_anomaly"] = True
    result.loc[global_flag, "_stat_reason"] = (
        f"Amount significantly above global average "
        f"(mean: ${result['amount'].mean():,.0f}, z>{ZSCORE_THRESHOLD})"
    )

    # Per-category anomaly
    if "expense_category" in result.columns:
        for cat, grp in result.groupby("expense_category"):
            if len(grp) < 3:
                continue
            cat_flag = _zscore_flags(grp["amount"])
            for idx in grp[cat_flag].index:
                if not result.at[idx, "_stat_anomaly"]:
                    result.at[idx, "_stat_anomaly"] = True
                    cat_mean = grp["amount"].mean()
                    result.at[idx, "_stat_reason"] = (
                        f"Unusually high for category '{cat}' "
                        f"(category avg: ${cat_mean:,.0f})"
                    )

    # Per-vendor anomaly
    if "vendor" in result.columns:
        for vendor, grp in result.groupby("vendor"):
            if len(grp) < 3:
                continue
            v_flag = _zscore_flags(grp["amount"])
            for idx in grp[v_flag].index:
                if not result.at[idx, "_stat_anomaly"]:
                    result.at[idx, "_stat_anomaly"] = True
                    v_mean = grp["amount"].mean()
                    result.at[idx, "_stat_reason"] = (
                        f"Unusually high for vendor '{vendor}' "
                        f"(vendor avg: ${v_mean:,.0f})"
                    )

    return result


def isolation_forest_anomaly(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    """
    Isolation Forest anomaly detection on numeric + encoded categorical features.
    Returns the input df with '_if_anomaly' (bool) and '_if_score' columns.
    Only runs when len(df) >= MIN_ROWS_FOR_ML.
    """
    result = df.copy()
    result["_if_anomaly"] = False
    result["_if_score"] = np.nan

    if len(df) < MIN_ROWS_FOR_ML:
        return result

    features = pd.DataFrame(index=df.index)
    features["amount"] = df["amount"].fillna(0)

    if "expense_category" in df.columns:
        le = LabelEncoder()
        cat_filled = df["expense_category"].fillna("Unknown")
        features["category_enc"] = le.fit_transform(cat_filled.astype(str))

    if "vendor" in df.columns:
        le2 = LabelEncoder()
        vendor_filled = df["vendor"].fillna("Unknown")
        features["vendor_enc"] = le2.fit_transform(vendor_filled.astype(str))

    if "transaction_date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["transaction_date"]):
        features["day_of_week"] = df["transaction_date"].dt.dayofweek
        features["month"] = df["transaction_date"].dt.month

    try:
        clf = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
        preds = clf.fit_predict(features)
        scores = clf.decision_function(features)

        result["_if_anomaly"] = preds == -1
        result["_if_score"] = scores
    except Exception:
        pass  # Degrade gracefully

    return result


def run_anomaly_detection(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Full anomaly detection pipeline.
    Returns (flagged_df, summary).
    flagged_df contains only anomalous rows with flag metadata.
    """
    if df.empty:
        return pd.DataFrame(), {"total_flagged": 0, "stat_flags": 0, "ml_flags": 0}

    # Statistical
    stat_result = statistical_anomaly_detection(df)

    # ML (if enough data)
    ml_result = isolation_forest_anomaly(stat_result)

    # Combine: flagged if either method flags it
    ml_result["is_anomaly"] = ml_result["_stat_anomaly"] | ml_result["_if_anomaly"]
    ml_result["anomaly_reason"] = ml_result["_stat_reason"]

    # For IF-only flags, add a reason
    if_only = ml_result["_if_anomaly"] & ~ml_result["_stat_anomaly"]
    ml_result.loc[if_only, "anomaly_reason"] = (
        "Flagged by machine learning model as an unusual spending pattern "
        "(Isolation Forest score)"
    )

    ml_result["detection_method"] = "None"
    ml_result.loc[ml_result["_stat_anomaly"], "detection_method"] = "Statistical"
    ml_result.loc[ml_result["_if_anomaly"], "detection_method"] = "ML (Isolation Forest)"
    both = ml_result["_stat_anomaly"] & ml_result["_if_anomaly"]
    ml_result.loc[both, "detection_method"] = "Statistical + ML"

    flagged = ml_result[ml_result["is_anomaly"]].copy()
    flagged.drop(
        columns=["_stat_anomaly", "_stat_reason", "_if_anomaly", "_if_score"],
        errors="ignore",
        inplace=True,
    )

    summary = {
        "total_flagged": len(flagged),
        "stat_flags": int(ml_result["_stat_anomaly"].sum()),
        "ml_flags": int(ml_result["_if_anomaly"].sum()),
        "ml_available": len(df) >= MIN_ROWS_FOR_ML,
        "flagged_amount": flagged["amount"].sum() if not flagged.empty else 0,
    }

    return flagged, summary
