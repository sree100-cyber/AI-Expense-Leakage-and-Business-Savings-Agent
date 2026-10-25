"""
validation.py - Validate transaction records and produce a clean/rejected split.
"""
import pandas as pd
import numpy as np
from typing import Tuple, List, Dict
import re


# Fields considered critical (rows rejected if completely absent)
REQUIRED_FIELDS = ["transaction_date", "amount"]
OPTIONAL_FIELDS = ["vendor", "expense_category", "description", "payment_reference",
                   "payment_method", "department"]

MAX_AMOUNT = 1_000_000_000  # $1 billion — sanity cap
MIN_AMOUNT = 0.0


def validate_transactions(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict]]:
    """
    Validate a normalized DataFrame.
    Returns:
        clean_df      — rows passing all critical checks
        rejected_df   — rows with critical failures
        warnings      — list of {row_index, field, issue} for non-critical issues
    """
    rejection_reasons: List[str] = []
    warnings: List[Dict] = []

    df = df.copy()
    df.insert(0, "_row_num", range(1, len(df) + 1))
    reject_mask = pd.Series(False, index=df.index)

    # ── 1. Amount validation ─────────────────────────────────────────────────
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    bad_amount = df["amount"].isna()
    reject_mask |= bad_amount
    df.loc[bad_amount, "_reject_reason"] = "Invalid or missing amount"

    negative = df["amount"] < MIN_AMOUNT
    reject_mask |= negative
    df.loc[negative & ~bad_amount, "_reject_reason"] = "Negative amount"

    giant = df["amount"] > MAX_AMOUNT
    reject_mask |= giant
    df.loc[giant, "_reject_reason"] = "Amount exceeds sanity cap ($1B)"

    zero_amount = df["amount"] == 0
    for idx in df[zero_amount].index:
        warnings.append({
            "row": df.at[idx, "_row_num"],
            "field": "amount",
            "issue": "Zero-value transaction — verify if intentional",
        })

    # ── 2. Date validation ───────────────────────────────────────────────────
    date_col = df["transaction_date"].copy()
    df["transaction_date"] = pd.to_datetime(date_col, errors="coerce", dayfirst=False)

    # Try dayfirst for failed parses
    failed_dates = df["transaction_date"].isna() & date_col.notna()
    if failed_dates.any():
        retry = pd.to_datetime(date_col[failed_dates], errors="coerce", dayfirst=True)
        df.loc[failed_dates, "transaction_date"] = retry

    still_bad = df["transaction_date"].isna()
    reject_mask |= still_bad
    df.loc[still_bad & ~df.index.isin(df[bad_amount].index), "_reject_reason"] = "Invalid or missing date"

    # Future dates — warn only
    today = pd.Timestamp.today().normalize()
    future_mask = df["transaction_date"] > today
    for idx in df[future_mask].index:
        warnings.append({
            "row": df.at[idx, "_row_num"],
            "field": "transaction_date",
            "issue": f"Future date: {df.at[idx, 'transaction_date'].date() if pd.notna(df.at[idx, 'transaction_date']) else 'unknown'}",
        })

    # Very old dates
    old_date = pd.Timestamp("2000-01-01")
    old_mask = df["transaction_date"].notna() & (df["transaction_date"] < old_date)
    for idx in df[old_mask].index:
        warnings.append({
            "row": df.at[idx, "_row_num"],
            "field": "transaction_date",
            "issue": f"Unusually old date: {df.at[idx, 'transaction_date'].date()}",
        })

    # ── 3. Duplicate transaction IDs ────────────────────────────────────────
    dup_ids = df["transaction_id"].duplicated(keep=False) & df["transaction_id"].notna()
    for idx in df[dup_ids].index:
        warnings.append({
            "row": df.at[idx, "_row_num"],
            "field": "transaction_id",
            "issue": f"Duplicate transaction_id: {df.at[idx, 'transaction_id']}",
        })

    # ── 4. Missing optional fields ──────────────────────────────────────────
    for field in OPTIONAL_FIELDS:
        if field in df.columns:
            missing_mask = df[field].isna() | (df[field].astype(str).str.strip() == "")
            for idx in df[missing_mask].index:
                if not reject_mask[idx]:
                    warnings.append({
                        "row": df.at[idx, "_row_num"],
                        "field": field,
                        "issue": f"Missing value for optional field '{field}'",
                    })

    # ── 5. Split clean / rejected ────────────────────────────────────────────
    rejected_df = df[reject_mask].copy()
    clean_df = df[~reject_mask].copy()
    clean_df.drop(columns=["_reject_reason", "_row_num"], errors="ignore", inplace=True)
    clean_df.reset_index(drop=True, inplace=True)
    rejected_df.reset_index(drop=True, inplace=True)

    return clean_df, rejected_df, warnings


def validation_summary(
    original_count: int,
    clean_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
    warnings: List[Dict],
) -> Dict:
    """Build a human-readable validation summary dict."""
    return {
        "total_uploaded": original_count,
        "accepted": len(clean_df),
        "rejected": len(rejected_df),
        "warnings": len(warnings),
        "acceptance_rate": round(len(clean_df) / max(original_count, 1) * 100, 1),
        "date_range": (
            f"{clean_df['transaction_date'].min().date()} to {clean_df['transaction_date'].max().date()}"
            if not clean_df.empty and clean_df["transaction_date"].notna().any()
            else "N/A"
        ),
        "total_amount": clean_df["amount"].sum() if not clean_df.empty else 0.0,
    }
