"""
duplicate_detection.py - Detect exact and possible duplicate payments.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import timedelta


def detect_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect rows with an identical payment_reference (non-null, non-empty).
    Returns a DataFrame of duplicate groups with 'duplicate_group_id' and 'duplicate_type'.
    """
    if df.empty:
        return pd.DataFrame()

    results = []
    ref_col = df["payment_reference"].astype(str).str.strip()
    valid_refs = ref_col[ref_col.notna() & (ref_col != "") & (ref_col.str.lower() != "nan")]

    dup_refs = valid_refs[valid_refs.duplicated(keep=False)]
    if dup_refs.empty:
        return pd.DataFrame()

    group_id = 1
    for ref_val in dup_refs.unique():
        mask = ref_col == ref_val
        group_df = df[mask].copy()
        group_df["duplicate_group_id"] = f"EX-{group_id:04d}"
        group_df["duplicate_type"] = "Exact (Payment Reference)"
        group_df["match_reason"] = f"Identical payment reference: '{ref_val}'"
        group_df["confidence"] = "High"
        results.append(group_df)
        group_id += 1

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


def detect_possible_duplicates(
    df: pd.DataFrame,
    date_tolerance_days: int = 3,
    amount_tolerance_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Detect possible duplicates by matching:
      - Same vendor + same amount + date within tolerance
    Returns a DataFrame of flagged rows with metadata.
    Distinct from exact duplicate detection.
    """
    if df.empty:
        return pd.DataFrame()

    # Only look at rows with vendor and amount
    working = df.copy()
    working = working[
        working["vendor"].notna()
        & working["amount"].notna()
        & working["transaction_date"].notna()
    ].copy()

    if len(working) < 2:
        return pd.DataFrame()

    working["_vendor_norm"] = working["vendor"].str.lower().str.strip()
    working["_date"] = pd.to_datetime(working["transaction_date"])

    results = []
    group_id = 1
    visited = set()

    records = working.reset_index(drop=True)
    for i in range(len(records)):
        if i in visited:
            continue
        row_i = records.iloc[i]
        group_indices = [i]

        for j in range(i + 1, len(records)):
            if j in visited:
                continue
            row_j = records.iloc[j]

            # Same vendor (normalized)
            if row_i["_vendor_norm"] != row_j["_vendor_norm"]:
                continue

            # Same or similar amount
            amt_diff_pct = abs(row_i["amount"] - row_j["amount"]) / max(row_i["amount"], 0.01)
            if amt_diff_pct > amount_tolerance_pct:
                continue

            # Date within tolerance
            date_diff = abs((row_i["_date"] - row_j["_date"]).days)
            if date_diff > date_tolerance_days:
                continue

            group_indices.append(j)

        if len(group_indices) > 1:
            for idx in group_indices:
                visited.add(idx)
            group_rows = records.iloc[group_indices].copy()
            group_rows["duplicate_group_id"] = f"PD-{group_id:04d}"
            group_rows["duplicate_type"] = "Possible (Vendor + Amount + Date)"
            group_rows["match_reason"] = (
                f"Same vendor '{row_i['vendor']}', amount ${row_i['amount']:,.2f}, "
                f"dates within {date_tolerance_days} day(s)"
            )
            group_rows["confidence"] = "Medium" if date_diff > 0 else "High"
            results.append(group_rows)
            group_id += 1

    if results:
        out = pd.concat(results, ignore_index=True)
        out.drop(columns=["_vendor_norm", "_date"], errors="ignore", inplace=True)
        return out
    return pd.DataFrame()


def run_duplicate_detection(
    df: pd.DataFrame,
    date_tolerance_days: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Run both exact and possible duplicate detection.
    Returns (exact_dups, possible_dups, summary_dict).
    """
    exact = detect_exact_duplicates(df)
    possible = detect_possible_duplicates(df, date_tolerance_days=date_tolerance_days)

    # Remove from "possible" any that are already in "exact"
    if not exact.empty and not possible.empty:
        exact_ids = set(exact["transaction_id"].dropna().astype(str))
        possible = possible[~possible["transaction_id"].astype(str).isin(exact_ids)]

    summary = {
        "exact_duplicate_groups": exact["duplicate_group_id"].nunique() if not exact.empty else 0,
        "exact_duplicate_transactions": len(exact),
        "possible_duplicate_groups": possible["duplicate_group_id"].nunique() if not possible.empty else 0,
        "possible_duplicate_transactions": len(possible),
        "total_at_risk_amount": (
            (exact["amount"].sum() if not exact.empty else 0)
            + (possible["amount"].sum() if not possible.empty else 0)
        ),
    }

    return exact, possible, summary
