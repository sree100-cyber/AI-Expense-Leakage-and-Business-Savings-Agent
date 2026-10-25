"""
expense_trends.py - Monthly trend analysis, recurring expense detection.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import timedelta


def compute_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute monthly total spending by category, vendor, and department.
    Returns a pivot-style DataFrame indexed by (year_month, category/vendor/dept).
    """
    if df.empty:
        return pd.DataFrame()

    result = df.copy()
    result["year_month"] = result["transaction_date"].dt.to_period("M")

    monthly = (
        result.groupby(["year_month", "expense_category"])["amount"]
        .sum()
        .reset_index()
    )
    monthly["year_month_str"] = monthly["year_month"].astype(str)
    return monthly


def compute_monthly_total(df: pd.DataFrame) -> pd.DataFrame:
    """Total spending per calendar month (all categories combined)."""
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["year_month"] = df["transaction_date"].dt.to_period("M")
    monthly = df.groupby("year_month")["amount"].sum().reset_index()
    monthly["year_month_str"] = monthly["year_month"].astype(str)
    return monthly.sort_values("year_month")


def compute_vendor_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly spending per vendor."""
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["year_month"] = df["transaction_date"].dt.to_period("M")
    return (
        df.groupby(["year_month", "vendor"])["amount"]
        .sum()
        .reset_index()
        .assign(year_month_str=lambda x: x["year_month"].astype(str))
        .sort_values(["vendor", "year_month"])
    )


def compute_dept_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Total spending per department."""
    if df.empty or "department" not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby("department")["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )


def detect_spending_increases(
    monthly_cat: pd.DataFrame,
    threshold_pct: float = 25.0,
) -> List[Dict]:
    """
    Identify categories where month-over-month spending increased by >= threshold_pct.
    Returns list of finding dicts.
    Requires at least 2 months of data per category.
    """
    findings = []
    if monthly_cat.empty:
        return findings

    for cat, grp in monthly_cat.groupby("expense_category"):
        grp = grp.sort_values("year_month")
        if len(grp) < 2:
            continue
        for i in range(1, len(grp)):
            prev = grp.iloc[i - 1]
            curr = grp.iloc[i]
            if prev["amount"] <= 0:
                continue
            pct_change = (curr["amount"] - prev["amount"]) / prev["amount"] * 100
            if pct_change >= threshold_pct:
                findings.append({
                    "category": cat,
                    "previous_month": str(prev["year_month"]),
                    "current_month": str(curr["year_month"]),
                    "previous_amount": prev["amount"],
                    "current_amount": curr["amount"],
                    "pct_increase": round(pct_change, 1),
                    "increase_amount": curr["amount"] - prev["amount"],
                })
    return findings


def detect_recurring_expenses(df: pd.DataFrame, min_occurrences: int = 2) -> pd.DataFrame:
    """
    Detect vendors that appear in multiple months with a similar amount —
    indicative of subscriptions or recurring payments.
    Returns a summary DataFrame.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["year_month"] = df["transaction_date"].dt.to_period("M")

    # Vendors appearing in ≥ min_occurrences distinct months
    vendor_months = (
        df.groupby("vendor")["year_month"]
        .nunique()
        .reset_index(name="months_active")
    )
    recurring_vendors = vendor_months[vendor_months["months_active"] >= min_occurrences]["vendor"]

    if recurring_vendors.empty:
        return pd.DataFrame()

    recurring_df = df[df["vendor"].isin(recurring_vendors)].copy()

    summary = (
        recurring_df.groupby("vendor")
        .agg(
            months_active=("year_month", "nunique"),
            total_transactions=("amount", "count"),
            total_amount=("amount", "sum"),
            avg_monthly_amount=("amount", lambda x: x.sum() / recurring_df.loc[x.index, "year_month"].nunique()),
            min_amount=("amount", "min"),
            max_amount=("amount", "max"),
            last_seen=("transaction_date", "max"),
        )
        .reset_index()
        .sort_values("total_amount", ascending=False)
    )

    # Flag amount consistency: std/mean < 0.1 → "Consistent (subscription-like)"
    amount_cv = (
        recurring_df.groupby("vendor")["amount"]
        .agg(lambda x: x.std() / x.mean() if x.mean() > 0 else 1)
        .reset_index(name="cv")
    )
    summary = summary.merge(amount_cv, on="vendor", how="left")
    summary["pattern"] = summary["cv"].apply(
        lambda cv: "Consistent (subscription-like)" if cv < 0.15 else "Variable (operational)"
    )

    return summary


def run_trend_analysis(df: pd.DataFrame) -> Dict:
    """
    Run full trend analysis and return a results dict.
    """
    if df.empty:
        return {
            "monthly_total": pd.DataFrame(),
            "monthly_by_category": pd.DataFrame(),
            "monthly_by_vendor": pd.DataFrame(),
            "dept_summary": pd.DataFrame(),
            "spending_increases": [],
            "recurring_expenses": pd.DataFrame(),
        }

    monthly_total = compute_monthly_total(df)
    monthly_cat = compute_monthly_summary(df)
    monthly_vendor = compute_vendor_monthly(df)
    dept_summary = compute_dept_summary(df)
    increases = detect_spending_increases(monthly_cat)
    recurring = detect_recurring_expenses(df)

    return {
        "monthly_total": monthly_total,
        "monthly_by_category": monthly_cat,
        "monthly_by_vendor": monthly_vendor,
        "dept_summary": dept_summary,
        "spending_increases": increases,
        "recurring_expenses": recurring,
    }
