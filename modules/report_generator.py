"""
report_generator.py - Generate downloadable Excel and CSV reports.
"""
import pandas as pd
import io
from typing import Dict, List, Optional
from datetime import datetime


def _safe_sheet_name(name: str) -> str:
    """Excel sheet names must be <= 31 chars and no special chars."""
    name = name.replace(":", "").replace("/", "-").replace("\\", "-")
    return name[:31]


def generate_excel_report(
    df_clean: pd.DataFrame,
    exact_dups: pd.DataFrame,
    possible_dups: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    recommendations: List[Dict],
    trends: Dict,
    currency: str = "USD",
    session_name: str = "Analysis",
) -> bytes:
    """
    Generate a consolidated Excel workbook with multiple sheets.
    Returns bytes that can be downloaded via st.download_button.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:

        # ── Sheet 1: Summary ─────────────────────────────────────────────────
        summary_data = {
            "Metric": [
                "Report Generated",
                "Session Name",
                "Currency",
                "Total Transactions",
                "Total Expenditure",
                "Date Range",
                "Exact Duplicate Groups",
                "Possible Duplicate Groups",
                "Unusual Transactions",
                "Total Recommendations",
                "Est. Monthly Savings Potential",
                "Est. Annual Savings Potential",
            ],
            "Value": [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                session_name,
                currency,
                len(df_clean),
                f"{df_clean['amount'].sum():,.2f}" if not df_clean.empty else "0",
                (
                    f"{df_clean['transaction_date'].min().date()} to {df_clean['transaction_date'].max().date()}"
                    if not df_clean.empty and df_clean["transaction_date"].notna().any()
                    else "N/A"
                ),
                exact_dups["duplicate_group_id"].nunique() if not exact_dups.empty else 0,
                possible_dups["duplicate_group_id"].nunique() if not possible_dups.empty else 0,
                len(anomaly_df),
                len(recommendations),
                f"{sum(r.get('monthly_savings',0) for r in recommendations):,.2f}",
                f"{sum(r.get('annual_savings',0) for r in recommendations):,.2f}",
            ],
        }
        pd.DataFrame(summary_data).to_excel(
            writer, sheet_name="Summary", index=False
        )

        # ── Sheet 2: Cleaned Transactions ────────────────────────────────────
        if not df_clean.empty:
            out = df_clean.copy()
            if "transaction_date" in out.columns:
                out["transaction_date"] = out["transaction_date"].dt.strftime("%Y-%m-%d")
            out.to_excel(writer, sheet_name="Cleaned Transactions", index=False)

        # ── Sheet 3: Duplicate Payments ──────────────────────────────────────
        dup_frames = []
        if not exact_dups.empty:
            ef = exact_dups.copy()
            if "transaction_date" in ef.columns:
                ef["transaction_date"] = ef["transaction_date"].dt.strftime("%Y-%m-%d")
            dup_frames.append(ef)
        if not possible_dups.empty:
            pf = possible_dups.copy()
            if "transaction_date" in pf.columns:
                pf["transaction_date"] = pf["transaction_date"].dt.strftime("%Y-%m-%d")
            dup_frames.append(pf)
        if dup_frames:
            pd.concat(dup_frames, ignore_index=True).to_excel(
                writer, sheet_name="Duplicate Payments", index=False
            )

        # ── Sheet 4: Anomalies ───────────────────────────────────────────────
        if not anomaly_df.empty:
            af = anomaly_df.copy()
            if "transaction_date" in af.columns:
                af["transaction_date"] = af["transaction_date"].dt.strftime("%Y-%m-%d")
            af.to_excel(writer, sheet_name="Unusual Transactions", index=False)

        # ── Sheet 5: Recommendations ─────────────────────────────────────────
        if recommendations:
            rec_df = pd.DataFrame([
                {
                    "ID": r.get("id", ""),
                    "Priority": r.get("priority", ""),
                    "Title": r.get("title", ""),
                    "Category": r.get("category", ""),
                    "Vendor": r.get("vendor", ""),
                    "Evidence": r.get("evidence", ""),
                    "Suggested Action": r.get("action", ""),
                    f"Est. Monthly Savings ({currency})": r.get("monthly_savings", 0),
                    f"Est. Annual Savings ({currency})": r.get("annual_savings", 0),
                    "Confidence": r.get("confidence", ""),
                    "Effort": r.get("effort", ""),
                    "Status": r.get("status", "Pending"),
                    "Assumption": r.get("assumption", ""),
                }
                for r in recommendations
            ])
            rec_df.to_excel(writer, sheet_name="Recommendations", index=False)

        # ── Sheet 6: Monthly Trends ──────────────────────────────────────────
        monthly_cat = trends.get("monthly_by_category", pd.DataFrame())
        if not monthly_cat.empty:
            mc = monthly_cat.copy()
            if "year_month" in mc.columns:
                mc["year_month"] = mc["year_month"].astype(str)
            mc.to_excel(writer, sheet_name="Monthly Category Trends", index=False)

        # ── Sheet 7: Recurring Expenses ──────────────────────────────────────
        recurring = trends.get("recurring_expenses", pd.DataFrame())
        if not recurring.empty:
            rc = recurring.copy()
            if "last_seen" in rc.columns:
                rc["last_seen"] = rc["last_seen"].dt.strftime("%Y-%m-%d")
            rc.to_excel(writer, sheet_name="Recurring Expenses", index=False)

        # ── Sheet 8: Disclaimer ──────────────────────────────────────────────
        disclaimer_data = {
            "Disclaimer": [
                "IMPORTANT: This report is generated by the AI Expense Leakage and Business Savings Agent.",
                "",
                "All findings are decision-support signals, NOT proof of fraud or confirmed financial loss.",
                "Savings estimates are projections based on documented assumptions and should not be recorded as",
                "actual realized savings until independently verified and implemented.",
                "",
                "Duplicate flags indicate transactions that WARRANT REVIEW — they do not confirm that",
                "overpayments occurred. Always cross-reference with original invoices and vendor statements.",
                "",
                "Anomaly flags indicate statistical outliers — not necessarily improper transactions.",
                "",
                "This tool does not provide financial, legal, or accounting advice.",
                "Consult a qualified financial professional before making significant financial decisions.",
                "",
                f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ]
        }
        pd.DataFrame(disclaimer_data).to_excel(
            writer, sheet_name="Disclaimer", index=False
        )

    return buf.getvalue()


def generate_duplicate_csv(exact_dups: pd.DataFrame, possible_dups: pd.DataFrame) -> bytes:
    """Generate a CSV of all duplicate-flagged transactions."""
    frames = []
    if not exact_dups.empty:
        frames.append(exact_dups)
    if not possible_dups.empty:
        frames.append(possible_dups)
    if not frames:
        return b"No duplicate transactions detected."
    combined = pd.concat(frames, ignore_index=True)
    if "transaction_date" in combined.columns:
        combined["transaction_date"] = combined["transaction_date"].dt.strftime("%Y-%m-%d")
    return combined.to_csv(index=False).encode()


def generate_anomaly_csv(anomaly_df: pd.DataFrame) -> bytes:
    """Generate a CSV of anomaly-flagged transactions."""
    if anomaly_df.empty:
        return b"No anomalies detected."
    out = anomaly_df.copy()
    if "transaction_date" in out.columns:
        out["transaction_date"] = out["transaction_date"].dt.strftime("%Y-%m-%d")
    return out.to_csv(index=False).encode()


def generate_recommendations_csv(recommendations: List[Dict], currency: str = "USD") -> bytes:
    """Generate a CSV of recommendations."""
    if not recommendations:
        return b"No recommendations generated."
    df = pd.DataFrame([
        {
            "ID": r.get("id", ""),
            "Priority": r.get("priority", ""),
            "Title": r.get("title", ""),
            "Category": r.get("category", ""),
            "Vendor": r.get("vendor", ""),
            "Evidence": r.get("evidence", ""),
            "Suggested Action": r.get("action", ""),
            f"Est Monthly Savings ({currency})": r.get("monthly_savings", 0),
            f"Est Annual Savings ({currency})": r.get("annual_savings", 0),
            "Confidence": r.get("confidence", ""),
            "Status": r.get("status", "Pending"),
        }
        for r in recommendations
    ])
    return df.to_csv(index=False).encode()
