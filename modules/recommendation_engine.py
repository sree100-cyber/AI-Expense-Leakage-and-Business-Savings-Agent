"""
recommendation_engine.py - Generate actionable savings recommendations.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional


PRIORITY_HIGH = "High"
PRIORITY_MED = "Medium"
PRIORITY_LOW = "Low"


def _safe_savings(amount: float, confidence_pct: float = 0.5) -> Tuple[float, float]:
    """Return (monthly_savings, annual_savings) applying a confidence discount."""
    monthly = max(amount * confidence_pct, 0)
    annual = monthly * 12
    return round(monthly, 2), round(annual, 2)


def recommendations_from_duplicates(
    exact_dups: pd.DataFrame,
    possible_dups: pd.DataFrame,
) -> List[Dict]:
    recs = []

    if not exact_dups.empty:
        groups = exact_dups["duplicate_group_id"].nunique()
        at_risk = exact_dups["amount"].sum()
        monthly, annual = _safe_savings(at_risk * 0.08, 1.0)  # assume 8% caught/month
        recs.append({
            "title": "Review Exact Duplicate Payments",
            "category": "Payment Controls",
            "vendor": "Multiple",
            "evidence": (
                f"{groups} group(s) of transactions share identical payment references, "
                f"totaling ${at_risk:,.2f} at risk."
            ),
            "action": (
                "Implement a payment deduplication check before processing. "
                "Cross-reference payment references in your AP system."
            ),
            "monthly_savings": monthly,
            "annual_savings": annual,
            "confidence": "High",
            "priority": PRIORITY_HIGH,
            "effort": "Low",
            "assumption": "Assumes ~8% of duplicate-reference transactions represent actual double payments per month.",
        })

    if not possible_dups.empty:
        groups = possible_dups["duplicate_group_id"].nunique()
        at_risk = possible_dups["amount"].sum()
        monthly, annual = _safe_savings(at_risk * 0.04, 0.7)
        recs.append({
            "title": "Investigate Possible Duplicate Payments",
            "category": "Payment Controls",
            "vendor": "Multiple",
            "evidence": (
                f"{groups} group(s) of transactions match the same vendor, amount, "
                f"and near-identical dates, totaling ${at_risk:,.2f}."
            ),
            "action": (
                "Review these transactions with the finance team. "
                "Request vendor statements to confirm no double billing."
            ),
            "monthly_savings": monthly,
            "annual_savings": annual,
            "confidence": "Medium",
            "priority": PRIORITY_HIGH,
            "effort": "Low",
            "assumption": "Assumes ~4% of flagged groups are genuine duplicate payments.",
        })

    return recs


def recommendations_from_anomalies(flagged_df: pd.DataFrame) -> List[Dict]:
    recs = []
    if flagged_df.empty:
        return recs

    top_anomalies = flagged_df.nlargest(5, "amount")
    for _, row in top_anomalies.iterrows():
        amount = row.get("amount", 0)
        cat = row.get("expense_category", "General")
        vendor = row.get("vendor", "Unknown")
        reason = row.get("anomaly_reason", "Statistically unusual amount")
        monthly, annual = _safe_savings(amount * 0.05, 0.6)

        recs.append({
            "title": f"Investigate Unusual Expense: {vendor}",
            "category": cat,
            "vendor": vendor,
            "evidence": f"${amount:,.2f} was flagged as unusual. Reason: {reason}",
            "action": (
                "Request invoice and approval documentation for this transaction. "
                "Verify it aligns with approved budget."
            ),
            "monthly_savings": monthly,
            "annual_savings": annual,
            "confidence": "Medium",
            "priority": PRIORITY_HIGH if amount > 5000 else PRIORITY_MED,
            "effort": "Medium",
            "assumption": "Assumes 5% of the flagged amount could be recovered through review.",
        })

    return recs


def recommendations_from_spending_increases(increases: List[Dict]) -> List[Dict]:
    recs = []
    seen_categories = set()

    for inc in sorted(increases, key=lambda x: x.get("pct_increase", 0), reverse=True)[:5]:
        cat = inc.get("category", "Unknown")
        if cat in seen_categories:
            continue
        seen_categories.add(cat)

        increase_amt = inc.get("increase_amount", 0)
        pct = inc.get("pct_increase", 0)
        monthly, annual = _safe_savings(increase_amt * 0.15, 0.6)

        recs.append({
            "title": f"Review Spending Spike: {cat}",
            "category": cat,
            "vendor": "Multiple",
            "evidence": (
                f"'{cat}' spending increased {pct:.1f}% from "
                f"{inc.get('previous_month', 'N/A')} to {inc.get('current_month', 'N/A')} "
                f"(+${increase_amt:,.2f})."
            ),
            "action": (
                "Identify the drivers behind this increase. "
                "Consider setting monthly budget alerts for this category."
            ),
            "monthly_savings": monthly,
            "annual_savings": annual,
            "confidence": "Medium",
            "priority": PRIORITY_HIGH if pct > 50 else PRIORITY_MED,
            "effort": "Medium",
            "assumption": "Assumes 15% of the excess spend above trend could be optimized.",
        })

    return recs


def recommendations_from_recurring(recurring_df: pd.DataFrame) -> List[Dict]:
    recs = []
    if recurring_df.empty:
        return recs

    # Focus on consistent (subscription-like) high-cost recurring vendors
    subscriptions = recurring_df[recurring_df["pattern"] == "Consistent (subscription-like)"]
    subscriptions = subscriptions.nlargest(5, "avg_monthly_amount")

    seen_vendors = set()
    for _, row in subscriptions.iterrows():
        vendor = row.get("vendor", "Unknown")
        if vendor in seen_vendors:
            continue
        seen_vendors.add(vendor)

        monthly_amt = row.get("avg_monthly_amount", 0)
        months = row.get("months_active", 1)
        monthly, annual = _safe_savings(monthly_amt * 0.1, 0.5)

        recs.append({
            "title": f"Audit Recurring Subscription: {vendor}",
            "category": "Subscriptions",
            "vendor": vendor,
            "evidence": (
                f"'{vendor}' appears consistently for {months} month(s) "
                f"at an average of ${monthly_amt:,.2f}/month."
            ),
            "action": (
                "Verify this subscription is actively used and provides value. "
                "Consider downgrading tiers or negotiating an annual rate."
            ),
            "monthly_savings": monthly,
            "annual_savings": annual,
            "confidence": "Low",
            "priority": PRIORITY_MED,
            "effort": "Low",
            "assumption": (
                "Assumes 10% of subscription cost could be saved through renegotiation "
                "or tier optimization. User confirmation required before action."
            ),
        })

    # High-cost variable recurring vendors — suggest vendor comparison
    variable = recurring_df[recurring_df["pattern"] == "Variable (operational)"]
    variable = variable.nlargest(3, "total_amount")
    for _, row in variable.iterrows():
        vendor = row.get("vendor", "Unknown")
        if vendor in seen_vendors:
            continue
        seen_vendors.add(vendor)

        total = row.get("total_amount", 0)
        monthly_avg = row.get("avg_monthly_amount", 0)
        monthly, annual = _safe_savings(monthly_avg * 0.08, 0.5)

        recs.append({
            "title": f"Compare Vendor Quotes: {vendor}",
            "category": "Procurement",
            "vendor": vendor,
            "evidence": (
                f"'{vendor}' has recurring spend of ${monthly_avg:,.2f}/month "
                f"(${total:,.2f} total) with variable amounts."
            ),
            "action": (
                "Request competing quotes from at least 2 alternative suppliers "
                "for this service or product category."
            ),
            "monthly_savings": monthly,
            "annual_savings": annual,
            "confidence": "Low",
            "priority": PRIORITY_LOW,
            "effort": "Medium",
            "assumption": "Assumes 8% savings potential through competitive sourcing.",
        })

    return recs


def deduplicate_recommendations(recs: List[Dict]) -> List[Dict]:
    """
    Remove recommendations where the same (title + category) pair appears more than once.
    Prevents double-counting the same saving.
    """
    seen = set()
    unique = []
    for rec in recs:
        key = (rec.get("title", ""), rec.get("category", ""))
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    return unique


def generate_recommendations(
    df: pd.DataFrame,
    exact_dups: pd.DataFrame,
    possible_dups: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    spending_increases: List[Dict],
    recurring_df: pd.DataFrame,
) -> List[Dict]:
    """
    Generate all recommendations from all detection modules.
    De-duplicates and assigns a unique recommendation_id to each.
    """
    all_recs = []
    all_recs.extend(recommendations_from_duplicates(exact_dups, possible_dups))
    all_recs.extend(recommendations_from_anomalies(anomaly_df))
    all_recs.extend(recommendations_from_spending_increases(spending_increases))
    all_recs.extend(recommendations_from_recurring(recurring_df))

    unique_recs = deduplicate_recommendations(all_recs)

    # Sort: High first, then by monthly savings descending
    priority_order = {PRIORITY_HIGH: 0, PRIORITY_MED: 1, PRIORITY_LOW: 2}
    unique_recs.sort(
        key=lambda r: (priority_order.get(r.get("priority", "Low"), 3), -r.get("monthly_savings", 0))
    )

    # Assign IDs
    for i, rec in enumerate(unique_recs, start=1):
        rec["id"] = i
        rec.setdefault("status", "Pending")

    return unique_recs


def compute_savings_totals(recs: List[Dict]) -> Dict:
    """
    Compute aggregate savings figures from recommendations.
    Only sums each saving once (de-duplication already done upstream).
    """
    total_monthly = sum(r.get("monthly_savings", 0) for r in recs)
    total_annual = sum(r.get("annual_savings", 0) for r in recs)
    high_priority = [r for r in recs if r.get("priority") == PRIORITY_HIGH]
    accepted = [r for r in recs if r.get("status") == "Accepted"]
    implemented = [r for r in recs if r.get("status") == "Implemented"]

    return {
        "total_recommendations": len(recs),
        "estimated_monthly_savings": round(total_monthly, 2),
        "estimated_annual_savings": round(total_annual, 2),
        "high_priority_count": len(high_priority),
        "accepted_monthly": round(sum(r.get("monthly_savings", 0) for r in accepted), 2),
        "implemented_monthly": round(sum(r.get("monthly_savings", 0) for r in implemented), 2),
    }
