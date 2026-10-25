"""
app.py - AI Expense Leakage and Business Savings Agent
Main Streamlit application entry point.

Run: streamlit run app.py
"""
import os
import sys
import warnings
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))
warnings.filterwarnings("ignore")

# ── Module imports ────────────────────────────────────────────────────────────
from modules.database import init_db, save_session, get_sessions, upsert_recommendation, get_recommendations, update_recommendation_status, upsert_category_threshold, get_category_thresholds
from modules.data_loader import load_dataframe, map_and_normalize, generate_transaction_ids
from modules.validation import validate_transactions, validation_summary
from modules.duplicate_detection import run_duplicate_detection
from modules.anomaly_detection import run_anomaly_detection
from modules.expense_trends import run_trend_analysis
from modules.recommendation_engine import generate_recommendations, compute_savings_totals
from modules.conversational_agent import RuleBasedAgent, get_answer
from modules.report_generator import (
    generate_excel_report, generate_duplicate_csv,
    generate_anomaly_csv, generate_recommendations_csv,
)

# ── DB Init ───────────────────────────────────────────────────────────────────
init_db()

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Expense Leakage & Savings Agent",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Global */
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
    h1 { color: #1E293B; font-size: 1.8rem !important; font-weight: 700; }
    h2 { color: #1E293B; font-size: 1.3rem !important; font-weight: 600; }
    h3 { color: #334155; font-size: 1.05rem !important; font-weight: 600; }

    /* Metric cards */
    .metric-card {
        background: #FFFFFF; border: 1px solid #E2E8F0;
        border-radius: 12px; padding: 1.2rem 1.4rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #1E293B; margin: 0; }
    .metric-label { font-size: 0.78rem; color: #64748B; text-transform: uppercase;
                    letter-spacing: 0.05em; margin-bottom: 0.3rem; }
    .metric-delta { font-size: 0.82rem; margin-top: 0.2rem; }
    .delta-pos { color: #059669; } .delta-neg { color: #DC2626; }

    /* Alert badges */
    .badge-high { background: #FEE2E2; color: #991B1B; padding: 2px 8px;
                  border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
    .badge-med  { background: #FEF3C7; color: #92400E; padding: 2px 8px;
                  border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
    .badge-low  { background: #DBEAFE; color: #1E40AF; padding: 2px 8px;
                  border-radius: 20px; font-size: 0.75rem; font-weight: 600; }

    /* Rec cards */
    .rec-card {
        background: #F8FAFC; border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB; border-radius: 8px;
        padding: 1rem 1.2rem; margin-bottom: 0.8rem;
    }
    .rec-card-high { border-left-color: #DC2626; }
    .rec-card-med  { border-left-color: #D97706; }
    .rec-card-low  { border-left-color: #2563EB; }

    /* Chat bubbles */
    .chat-user { background: #2563EB; color: white; border-radius: 18px 18px 4px 18px;
                 padding: 0.7rem 1rem; margin: 0.4rem 0; max-width: 80%; margin-left: auto;
                 font-size: 0.9rem; }
    .chat-agent { background: #F1F5F9; color: #1E293B; border-radius: 18px 18px 18px 4px;
                  padding: 0.7rem 1rem; margin: 0.4rem 0; max-width: 85%; font-size: 0.9rem; }
    .chat-source { font-size: 0.7rem; color: #94A3B8; margin-top: 2px; }

    /* Disclaimer */
    .disclaimer-box { background: #FFF7ED; border: 1px solid #FDBA74;
                      border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.82rem;
                      color: #78350F; margin-top: 1rem; }
    /* Sidebar */
    .sidebar-header { font-size: 1.1rem; font-weight: 700; color: #1E293B; margin-bottom: 0.5rem; }
    .data-status-ok  { color: #059669; font-size: 0.82rem; }
    .data-status-err { color: #DC2626; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)


# ── Session State Helpers ─────────────────────────────────────────────────────
def init_session():
    defaults = {
        "df_clean": None,
        "df_rejected": None,
        "validation_warnings": [],
        "validation_summary": {},
        "exact_dups": pd.DataFrame(),
        "possible_dups": pd.DataFrame(),
        "dup_summary": {},
        "anomaly_df": pd.DataFrame(),
        "anomaly_summary": {},
        "trends": {},
        "recommendations": [],
        "session_id": None,
        "currency": "USD",
        "filename": None,
        "chat_history": [],
        "analysis_done": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def run_full_analysis(df: pd.DataFrame, currency: str, filename: str):
    """Run the complete analysis pipeline and store results in session state."""
    with st.spinner("Running full analysis pipeline..."):
        # Duplicate detection
        exact, possible, dup_sum = run_duplicate_detection(df)
        st.session_state.exact_dups = exact
        st.session_state.possible_dups = possible
        st.session_state.dup_summary = dup_sum

        # Anomaly detection
        anomaly_df, anomaly_sum = run_anomaly_detection(df)
        st.session_state.anomaly_df = anomaly_df
        st.session_state.anomaly_summary = anomaly_sum

        # Trend analysis
        trends = run_trend_analysis(df)
        st.session_state.trends = trends

        # Recommendations
        recs = generate_recommendations(
            df=df,
            exact_dups=exact,
            possible_dups=possible,
            anomaly_df=anomaly_df,
            spending_increases=trends.get("spending_increases", []),
            recurring_df=trends.get("recurring_expenses", pd.DataFrame()),
        )
        st.session_state.recommendations = recs

        # Save session to DB
        session_id = save_session(
            filename=filename,
            total_rows=len(st.session_state.df_clean) + len(st.session_state.df_rejected or []),
            accepted_rows=len(df),
            rejected_rows=len(st.session_state.df_rejected or []),
            total_amount=float(df["amount"].sum()),
            currency=currency,
        )
        st.session_state.session_id = session_id

        # Persist recommendations to DB
        for rec in recs:
            upsert_recommendation(
                session_id=session_id,
                title=rec["title"],
                category=rec.get("category", ""),
                status=rec.get("status", "Pending"),
                monthly_savings=rec.get("monthly_savings", 0),
                annual_savings=rec.get("annual_savings", 0),
                priority=rec.get("priority", "Low"),
            )

        st.session_state.analysis_done = True
    st.success("Analysis complete!")


def load_sample_data():
    """Load the built-in synthetic sample dataset."""
    sample_path = os.path.join(ROOT_DIR, "data", "sample_expenses.csv")
    if not os.path.exists(sample_path):
        st.error("Sample data file not found. Run: python generate_sample_data.py")
        return
    df_raw, err = load_dataframe(open(sample_path, "rb"), "sample_expenses.csv")
    if err:
        st.error(f"Could not load sample data: {err}")
        return
    process_upload(df_raw, "sample_expenses.csv", st.session_state.currency)


def process_upload(df_raw: pd.DataFrame, filename: str, currency: str):
    """Map, validate, and trigger analysis."""
    df_mapped, mapping = map_and_normalize(df_raw)
    df_mapped = generate_transaction_ids(df_mapped)
    clean, rejected, warnings = validate_transactions(df_mapped)
    vs = validation_summary(len(df_raw), clean, rejected, warnings)

    st.session_state.df_clean = clean
    st.session_state.df_rejected = rejected
    st.session_state.validation_warnings = warnings
    st.session_state.validation_summary = vs
    st.session_state.currency = currency
    st.session_state.filename = filename
    st.session_state.analysis_done = False

    if clean.empty:
        st.error("No valid rows found after validation. Check the data format.")
        return

    run_full_analysis(clean, currency, filename)


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown('<p class="sidebar-header">💰 Expense Savings Agent</p>', unsafe_allow_html=True)
        st.caption("AI-powered financial leakage detection")
        st.divider()

        page = st.radio(
            "Navigation",
            ["Overview Dashboard", "Upload Expenses", "Transaction Analysis",
             "Anomaly Detection", "Savings Recommendations", "Expense Assistant",
             "Reports & Test Results", "About the Agent"],
            label_visibility="collapsed",
        )

        st.divider()
        if st.session_state.df_clean is not None:
            vs = st.session_state.validation_summary
            st.markdown(f'<p class="data-status-ok">Dataset loaded: {st.session_state.filename}</p>', unsafe_allow_html=True)
            st.caption(f"{vs.get('accepted',0):,} transactions | {st.session_state.currency}")
        else:
            st.markdown('<p class="data-status-err">No dataset loaded</p>', unsafe_allow_html=True)
            st.caption("Upload or load sample data")

        st.divider()
        currency = st.selectbox(
            "Currency", ["USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD"],
            index=0
        )
        if currency != st.session_state.currency:
            st.session_state.currency = currency

        st.divider()
        st.caption("⚠️ Findings are decision-support signals, not proof of fraud or financial advice.")

    return page


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE RENDERERS
# ═══════════════════════════════════════════════════════════════════════════════

def metric_card(label, value, delta=None, delta_positive=True, prefix=""):
    delta_html = ""
    if delta is not None:
        cls = "delta-pos" if delta_positive else "delta-neg"
        arrow = "▲" if delta_positive else "▼"
        delta_html = f'<p class="metric-delta {cls}">{arrow} {delta}</p>'
    return f"""
    <div class="metric-card">
        <p class="metric-label">{label}</p>
        <p class="metric-value">{prefix}{value}</p>
        {delta_html}
    </div>
    """


def render_overview():
    st.title("📊 Overview Dashboard")
    st.caption("Real-time financial analysis summary based on uploaded transaction data.")

    if st.session_state.df_clean is None:
        st.info("No dataset loaded. Go to **Upload Expenses** to get started, or load the sample data.")
        if st.button("Load Sample Dataset", type="primary"):
            load_sample_data()
            st.rerun()
        return

    df = st.session_state.df_clean
    vs = st.session_state.validation_summary
    dup_sum = st.session_state.dup_summary
    anomaly_sum = st.session_state.anomaly_summary
    recs = st.session_state.recommendations
    savings = compute_savings_totals(recs)
    cur = st.session_state.currency

    # ── KPI row ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    total = df["amount"].sum()
    n = len(df)
    dup_groups = dup_sum.get("exact_duplicate_groups", 0) + dup_sum.get("possible_duplicate_groups", 0)
    anomalies = anomaly_sum.get("total_flagged", 0)
    est_savings = savings.get("estimated_annual_savings", 0)

    cards = [
        (c1, "Total Expenditure", f"{total:,.0f}", cur),
        (c2, "Transactions Analysed", f"{n:,}", ""),
        (c3, "Duplicate Groups", f"{dup_groups}", "⚠️ " if dup_groups > 0 else ""),
        (c4, "Unusual Transactions", f"{anomalies}", "🔴 " if anomalies > 0 else ""),
        (c5, "Recommendations", f"{len(recs)}", ""),
        (c6, "Est. Annual Savings", f"{est_savings:,.0f}", cur),
    ]
    for col, label, value, prefix in cards:
        with col:
            st.markdown(metric_card(label, value, prefix=prefix), unsafe_allow_html=True)

    st.divider()

    # ── Charts ────────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monthly Expense Trend")
        monthly = st.session_state.trends.get("monthly_total", pd.DataFrame())
        if not monthly.empty:
            fig = px.area(
                monthly, x="year_month_str", y="amount",
                labels={"year_month_str": "Month", "amount": f"Amount ({cur})"},
                color_discrete_sequence=["#2563EB"],
                template="plotly_white",
            )
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=280)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data for trend chart.")

    with col2:
        st.subheader("Spending by Category")
        if "expense_category" in df.columns:
            cat_data = df.groupby("expense_category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
            fig = px.pie(
                cat_data, values="amount", names="expense_category",
                color_discrete_sequence=px.colors.qualitative.Set3,
                template="plotly_white",
            )
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=280)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Top Vendors by Expenditure")
        if "vendor" in df.columns:
            vendor_data = df.groupby("vendor")["amount"].sum().reset_index().nlargest(10, "amount")
            fig = px.bar(
                vendor_data, x="amount", y="vendor", orientation="h",
                labels={"amount": f"Amount ({cur})", "vendor": "Vendor"},
                color="amount", color_continuous_scale="Blues",
                template="plotly_white",
            )
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300,
                              yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Department Spending")
        dept = st.session_state.trends.get("dept_summary", pd.DataFrame())
        if not dept.empty and "department" in dept.columns:
            fig = px.bar(
                dept, x="department", y="amount",
                labels={"department": "Department", "amount": f"Amount ({cur})"},
                color="amount", color_continuous_scale="Purples",
                template="plotly_white",
            )
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No department data available.")

    # ── Findings quick summary ────────────────────────────────────────────────
    st.subheader("Key Findings at a Glance")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("**Anomaly Distribution**")
        anomaly_df = st.session_state.anomaly_df
        if not anomaly_df.empty and "detection_method" in anomaly_df.columns:
            method_counts = anomaly_df["detection_method"].value_counts().reset_index()
            method_counts.columns = ["Method", "Count"]
            fig = px.bar(method_counts, x="Method", y="Count",
                         color="Count", color_continuous_scale="Reds",
                         template="plotly_white")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=220, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No anomalies detected in the current dataset.")

    with col_f2:
        st.markdown("**Estimated Savings by Category**")
        if recs:
            rec_df = pd.DataFrame(recs)
            cat_sav = rec_df.groupby("category")["annual_savings"].sum().reset_index().sort_values("annual_savings", ascending=False)
            fig = px.bar(cat_sav, x="annual_savings", y="category", orientation="h",
                         labels={"annual_savings": f"Est. Annual ({cur})", "category": "Category"},
                         color="annual_savings", color_continuous_scale="Greens",
                         template="plotly_white")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=220,
                              yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No recommendations generated yet.")

    st.markdown('<div class="disclaimer-box">⚠️ <b>Disclaimer:</b> All findings are decision-support signals. Estimated savings are projections based on documented assumptions, not guaranteed outcomes. Consult a qualified financial professional before acting on these insights.</div>', unsafe_allow_html=True)


def render_upload():
    st.title("📤 Upload Expenses")
    st.caption("Upload your business transaction data in CSV or Excel format.")

    col1, col2 = st.columns([2, 1])
    with col1:
        cur = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD"],
                           index=["USD","EUR","GBP","INR","AUD","CAD","SGD"].index(st.session_state.currency))
        uploaded = st.file_uploader(
            "Upload transaction file",
            type=["csv", "xlsx", "xls"],
            help="Max 50MB. Supported formats: CSV, Excel (.xlsx, .xls)"
        )
        if uploaded:
            if uploaded.size > 50 * 1024 * 1024:
                st.error("File exceeds 50MB limit.")
            else:
                if st.button("Process Upload", type="primary"):
                    df_raw, err = load_dataframe(uploaded, uploaded.name)
                    if err:
                        st.error(f"File error: {err}")
                    else:
                        process_upload(df_raw, uploaded.name, cur)
                        st.rerun()

    with col2:
        st.markdown("**Or use built-in demo data:**")
        st.caption("157 synthetic transactions across 12 months, with deliberately inserted duplicates, anomalies, and spending spikes. Clearly labeled as synthetic.")
        if st.button("Load Sample Dataset", type="secondary"):
            load_sample_data()
            st.rerun()

    # Supported column reference
    with st.expander("Supported Column Names & Mappings"):
        mapping_info = {
            "Canonical Name": ["transaction_id", "transaction_date", "vendor", "expense_category",
                                "description", "amount", "payment_reference", "payment_method", "department"],
            "Also Recognized As": [
                "txn_id, trans_id, id",
                "date, txn_date, invoice_date, payment_date",
                "vendor_name, supplier, merchant, payee",
                "category, expense_type, type, account",
                "memo, details, notes, narrative",
                "total, total_amount, value, cost, debit",
                "ref, reference, check_number, invoice_number",
                "method, pay_type, mode",
                "dept, division, team, cost_center",
            ]
        }
        st.dataframe(pd.DataFrame(mapping_info), use_container_width=True, hide_index=True)

    # Validation results
    if st.session_state.validation_summary:
        vs = st.session_state.validation_summary
        st.divider()
        st.subheader("Validation Results")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Uploaded", vs.get("total_uploaded", 0))
        with c2: st.metric("Accepted", vs.get("accepted", 0), delta=f"{vs.get('acceptance_rate',0):.1f}%")
        with c3: st.metric("Rejected", vs.get("rejected", 0))
        with c4: st.metric("Warnings", vs.get("warnings", 0))

        if vs.get("date_range"):
            st.caption(f"Date range: {vs['date_range']} | Total amount: {st.session_state.currency} {vs.get('total_amount', 0):,.2f}")

        if st.session_state.df_rejected is not None and not st.session_state.df_rejected.empty:
            with st.expander(f"View {len(st.session_state.df_rejected)} Rejected Rows"):
                st.dataframe(st.session_state.df_rejected, use_container_width=True)

        if st.session_state.validation_warnings:
            with st.expander(f"View {len(st.session_state.validation_warnings)} Warnings"):
                warn_df = pd.DataFrame(st.session_state.validation_warnings)
                st.dataframe(warn_df, use_container_width=True)


def render_transaction_analysis():
    st.title("🔍 Transaction Analysis")
    df = st.session_state.df_clean
    if df is None:
        st.info("Upload a dataset first.")
        return

    cur = st.session_state.currency

    # Filters
    with st.expander("Filters", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            cats = ["All"] + sorted(df["expense_category"].dropna().unique().tolist()) if "expense_category" in df.columns else ["All"]
            sel_cat = st.selectbox("Category", cats)
        with col2:
            depts = ["All"] + sorted(df["department"].dropna().unique().tolist()) if "department" in df.columns else ["All"]
            sel_dept = st.selectbox("Department", depts)
        with col3:
            if df["transaction_date"].notna().any():
                min_d = df["transaction_date"].min().date()
                max_d = df["transaction_date"].max().date()
                date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
            else:
                date_range = None

    filtered = df.copy()
    if sel_cat != "All":
        filtered = filtered[filtered["expense_category"] == sel_cat]
    if sel_dept != "All":
        filtered = filtered[filtered["department"] == sel_dept]
    if date_range and len(date_range) == 2:
        filtered = filtered[
            (filtered["transaction_date"].dt.date >= date_range[0]) &
            (filtered["transaction_date"].dt.date <= date_range[1])
        ]

    st.caption(f"Showing {len(filtered):,} of {len(df):,} transactions")

    # Monthly category trend
    st.subheader("Monthly Spending by Category")
    monthly_cat = st.session_state.trends.get("monthly_by_category", pd.DataFrame())
    if not monthly_cat.empty:
        if sel_cat != "All":
            plot_data = monthly_cat[monthly_cat["expense_category"] == sel_cat]
        else:
            plot_data = monthly_cat
        if not plot_data.empty:
            fig = px.bar(
                plot_data, x="year_month_str", y="amount", color="expense_category",
                labels={"year_month_str": "Month", "amount": f"Amount ({cur})", "expense_category": "Category"},
                template="plotly_white",
                barmode="stack",
            )
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=320)
            st.plotly_chart(fig, use_container_width=True)

    # Spending increases
    increases = st.session_state.trends.get("spending_increases", [])
    if increases:
        st.subheader(f"Spending Increases Detected ({len(increases)})")
        inc_df = pd.DataFrame(increases)
        inc_df = inc_df.rename(columns={
            "category": "Category", "previous_month": "From", "current_month": "To",
            "previous_amount": f"Prev ({cur})", "current_amount": f"Curr ({cur})",
            "pct_increase": "% Increase", "increase_amount": f"Delta ({cur})",
        })
        st.dataframe(
            inc_df.style.format({f"Prev ({cur})": "{:,.2f}", f"Curr ({cur})": "{:,.2f}",
                                  "% Increase": "{:.1f}%", f"Delta ({cur})": "{:,.2f}"}),
            use_container_width=True, hide_index=True,
        )

    # Full transaction table
    st.subheader("Transaction Detail")
    display_cols = [c for c in ["transaction_id", "transaction_date", "vendor", "expense_category",
                                  "department", "amount", "payment_method", "payment_reference", "description"]
                    if c in filtered.columns]
    disp = filtered[display_cols].copy()
    if "transaction_date" in disp.columns:
        disp["transaction_date"] = disp["transaction_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        disp.style.format({"amount": "{:,.2f}"}),
        use_container_width=True, hide_index=True
    )


def render_anomaly_detection():
    st.title("🚨 Anomaly Detection")
    df = st.session_state.df_clean

    if df is None:
        st.info("Upload a dataset first.")
        return

    cur = st.session_state.currency
    exact_dups = st.session_state.exact_dups
    possible_dups = st.session_state.possible_dups
    anomaly_df = st.session_state.anomaly_df
    dup_sum = st.session_state.dup_summary
    anomaly_sum = st.session_state.anomaly_summary

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Exact Duplicate Groups", dup_sum.get("exact_duplicate_groups", 0))
    with c2: st.metric("Possible Duplicate Groups", dup_sum.get("possible_duplicate_groups", 0))
    with c3: st.metric("Unusual Transactions", anomaly_sum.get("total_flagged", 0))
    with c4:
        at_risk = dup_sum.get("total_at_risk_amount", 0)
        st.metric(f"At-Risk Amount ({cur})", f"{at_risk:,.0f}")

    st.markdown('<div class="disclaimer-box">These flags are indicators for review — not confirmation of errors, fraud, or policy violations. Always verify findings against source documents before taking action.</div>', unsafe_allow_html=True)
    st.divider()

    tab1, tab2, tab3 = st.tabs(["Duplicate Payments", "Unusual Transactions", "ML Details"])

    with tab1:
        st.subheader("Exact Duplicate Payments")
        if exact_dups.empty:
            st.success("No exact duplicate payments detected.")
        else:
            st.warning(f"{dup_sum['exact_duplicate_groups']} group(s) of exact duplicates found.")
            disp = exact_dups.copy()
            if "transaction_date" in disp.columns:
                disp["transaction_date"] = disp["transaction_date"].dt.strftime("%Y-%m-%d")
            cols = [c for c in ["duplicate_group_id", "transaction_id", "transaction_date", "vendor",
                                  "amount", "payment_reference", "match_reason", "confidence"] if c in disp.columns]
            st.dataframe(disp[cols].style.format({"amount": "{:,.2f}"}), use_container_width=True, hide_index=True)

        st.subheader("Possible Duplicate Payments")
        if possible_dups.empty:
            st.success("No possible duplicates detected.")
        else:
            st.warning(f"{dup_sum['possible_duplicate_groups']} group(s) of possible duplicates found (vendor + amount match within 3 days).")
            disp2 = possible_dups.copy()
            if "transaction_date" in disp2.columns:
                disp2["transaction_date"] = disp2["transaction_date"].dt.strftime("%Y-%m-%d")
            cols2 = [c for c in ["duplicate_group_id", "transaction_id", "transaction_date", "vendor",
                                    "amount", "payment_reference", "match_reason", "confidence"] if c in disp2.columns]
            st.dataframe(disp2[cols2].style.format({"amount": "{:,.2f}"}), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Unusual Transactions")
        if anomaly_df.empty:
            st.success("No unusual transactions detected in the current dataset.")
        else:
            st.warning(f"{len(anomaly_df)} transaction(s) flagged as unusual.")
            disp3 = anomaly_df.copy()
            if "transaction_date" in disp3.columns:
                disp3["transaction_date"] = disp3["transaction_date"].dt.strftime("%Y-%m-%d")
            acols = [c for c in ["transaction_id", "transaction_date", "vendor", "expense_category",
                                    "amount", "anomaly_reason", "detection_method"] if c in disp3.columns]
            st.dataframe(
                disp3[acols].style.format({"amount": "{:,.2f}"}),
                use_container_width=True, hide_index=True,
            )
            # Amount distribution
            st.subheader("Amount Distribution (Flagged vs Normal)")
            normal_amounts = df[~df["transaction_id"].isin(anomaly_df["transaction_id"])]["amount"]
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=normal_amounts, name="Normal", opacity=0.7,
                                        marker_color="#2563EB", nbinsx=40))
            fig.add_trace(go.Histogram(x=anomaly_df["amount"], name="Flagged", opacity=0.8,
                                        marker_color="#DC2626", nbinsx=20))
            fig.update_layout(barmode="overlay", template="plotly_white", height=280,
                               margin=dict(l=0,r=0,t=20,b=0),
                               xaxis_title=f"Amount ({cur})", yaxis_title="Count")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("ML Detection Details")
        ml_avail = anomaly_sum.get("ml_available", False)
        if ml_avail:
            st.success(f"Isolation Forest model applied ({anomaly_sum.get('ml_flags', 0)} ML-flagged transactions).")
        else:
            st.info(f"Machine learning detection requires at least 20 transactions. Current dataset has {len(df)} rows.")
        st.caption(f"Statistical flags: {anomaly_sum.get('stat_flags', 0)} | ML flags: {anomaly_sum.get('ml_flags', 0)}")
        if not anomaly_df.empty and "detection_method" in anomaly_df.columns:
            method_counts = anomaly_df["detection_method"].value_counts().reset_index()
            method_counts.columns = ["Method", "Count"]
            fig = px.bar(method_counts, x="Method", y="Count",
                         color="Count", color_continuous_scale="Reds",
                         template="plotly_white")
            fig.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=220, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)


def render_recommendations():
    st.title("💡 Savings Recommendations")
    recs = st.session_state.recommendations
    cur = st.session_state.currency

    if not recs:
        st.info("No recommendations available. Upload a dataset to generate insights.")
        return

    savings = compute_savings_totals(recs)

    # Savings overview
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Recommendations", savings["total_recommendations"])
    with c2: st.metric(f"Est. Monthly Savings ({cur})", f"{savings['estimated_monthly_savings']:,.0f}")
    with c3: st.metric(f"Est. Annual Savings ({cur})", f"{savings['estimated_annual_savings']:,.0f}")
    with c4: st.metric("High Priority", savings["high_priority_count"])

    st.markdown('<div class="disclaimer-box">Savings estimates are projections based on documented assumptions. They represent <b>potential savings</b>, not confirmed or realized savings. Review each recommendation independently.</div>', unsafe_allow_html=True)
    st.divider()

    # Filter
    col1, col2 = st.columns(2)
    with col1:
        filter_priority = st.multiselect("Filter by Priority", ["High", "Medium", "Low"],
                                          default=["High", "Medium", "Low"])
    with col2:
        filter_status = st.multiselect("Filter by Status",
                                        ["Pending", "Accepted", "Rejected", "Implemented"],
                                        default=["Pending", "Accepted", "Implemented"])

    filtered_recs = [
        r for r in recs
        if r.get("priority") in filter_priority and r.get("status") in filter_status
    ]

    st.caption(f"Showing {len(filtered_recs)} of {len(recs)} recommendations")

    # Render each recommendation
    priority_colors = {"High": "rec-card-high", "Medium": "rec-card-med", "Low": "rec-card-low"}
    badge_classes = {"High": "badge-high", "Medium": "badge-med", "Low": "badge-low"}

    for rec in filtered_recs:
        prio = rec.get("priority", "Low")
        card_class = priority_colors.get(prio, "")
        badge_class = badge_classes.get(prio, "badge-low")

        with st.container():
            col_main, col_action = st.columns([5, 2])
            with col_main:
                st.markdown(f"""
                <div class="rec-card {card_class}">
                    <span class="{badge_class}">{prio} Priority</span>
                    &nbsp;&nbsp;<small style="color:#64748B">Confidence: {rec.get('confidence','?')} | Effort: {rec.get('effort','?')}</small>
                    <h3 style="margin:0.5rem 0 0.3rem 0">{rec.get('title','')}</h3>
                    <p style="margin:0;color:#475569;font-size:0.88rem">
                        <b>Category:</b> {rec.get('category','')} | <b>Vendor:</b> {rec.get('vendor','')}
                    </p>
                    <p style="margin:0.5rem 0 0.3rem 0;font-size:0.88rem"><b>Evidence:</b> {rec.get('evidence','')}</p>
                    <p style="margin:0;font-size:0.88rem"><b>Action:</b> {rec.get('action','')}</p>
                    <p style="margin:0.5rem 0 0;font-size:0.82rem;color:#64748B"><i>Assumption: {rec.get('assumption','')}</i></p>
                    <p style="margin:0.3rem 0 0;font-size:0.88rem;color:#059669">
                        Est. Monthly: <b>{cur} {rec.get('monthly_savings',0):,.0f}</b> &nbsp;|&nbsp;
                        Est. Annual: <b>{cur} {rec.get('annual_savings',0):,.0f}</b>
                    </p>
                </div>
                """, unsafe_allow_html=True)

            with col_action:
                rec_id = rec.get("id")
                current_status = rec.get("status", "Pending")
                new_status = st.selectbox(
                    "Status",
                    ["Pending", "Accepted", "Rejected", "Implemented"],
                    index=["Pending", "Accepted", "Rejected", "Implemented"].index(current_status),
                    key=f"status_{rec_id}",
                )
                notes = st.text_input("Notes", value="", key=f"notes_{rec_id}",
                                       placeholder="Optional notes...")
                if st.button("Save", key=f"save_{rec_id}", type="secondary"):
                    rec["status"] = new_status
                    if st.session_state.session_id:
                        db_recs = get_recommendations(st.session_state.session_id)
                        for db_rec in db_recs:
                            if db_rec["recommendation_title"] == rec["title"]:
                                update_recommendation_status(db_rec["id"], new_status, notes)
                                break
                    st.success("Status saved.")
                    st.rerun()

    # Savings by category chart
    if filtered_recs:
        st.divider()
        st.subheader("Savings Potential by Category")
        cat_sav = pd.DataFrame(filtered_recs).groupby("category")["annual_savings"].sum().reset_index()
        fig = px.bar(cat_sav, x="category", y="annual_savings",
                     labels={"category": "Category", "annual_savings": f"Est. Annual Savings ({cur})"},
                     color="annual_savings", color_continuous_scale="Greens",
                     template="plotly_white")
        fig.update_layout(margin=dict(l=0,r=0,t=20,b=0), height=260, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)


def render_assistant():
    st.title("🤖 Expense Assistant")
    st.caption("Ask questions about your uploaded transaction data. Answers are based on real analysis results.")

    df = st.session_state.df_clean
    if df is None:
        st.info("Upload a dataset first to use the assistant.")
        return

    # Suggested questions
    st.subheader("Suggested Questions")
    suggestions = [
        "Which category has the highest spending?",
        "Which transactions may be duplicates?",
        "What are the top 3 cost-saving opportunities?",
        "How much is spent on subscriptions each month?",
        "What should the business review first?",
        "How many anomalies were detected?",
        "What is the total expenditure?",
        "Which vendor has the highest spend?",
    ]
    cols = st.columns(4)
    for i, s in enumerate(suggestions):
        with cols[i % 4]:
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": s})
                context = {
                    "df": df,
                    "exact_dups": st.session_state.exact_dups,
                    "possible_dups": st.session_state.possible_dups,
                    "anomaly_df": st.session_state.anomaly_df,
                    "recommendations": st.session_state.recommendations,
                    "trends": st.session_state.trends,
                    "currency": st.session_state.currency,
                }
                answer, source = get_answer(s, context)
                st.session_state.chat_history.append({"role": "assistant", "content": answer, "source": source})
                st.rerun()

    st.divider()

    # Chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-user">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                src = msg.get("source", "Rule-based")
                st.markdown(f'<div class="chat-agent">{msg["content"]}<br><span class="chat-source">Source: {src}</span></div>', unsafe_allow_html=True)

    # Text input
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            user_input = st.text_input("Ask a question...", label_visibility="collapsed",
                                        placeholder="e.g. Which category has the highest spending?")
        with col2:
            submitted = st.form_submit_button("Ask", type="primary", use_container_width=True)

    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        context = {
            "df": df,
            "exact_dups": st.session_state.exact_dups,
            "possible_dups": st.session_state.possible_dups,
            "anomaly_df": st.session_state.anomaly_df,
            "recommendations": st.session_state.recommendations,
            "trends": st.session_state.trends,
            "currency": st.session_state.currency,
        }
        answer, source = get_answer(user_input, context)
        st.session_state.chat_history.append({"role": "assistant", "content": answer, "source": source})
        st.rerun()

    if st.session_state.chat_history:
        if st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()


def render_reports():
    st.title("📋 Reports & Test Results")
    df = st.session_state.df_clean
    cur = st.session_state.currency

    # ── Downloads ────────────────────────────────────────────────────────────
    st.subheader("Download Reports")
    if df is None:
        st.info("Upload a dataset to generate downloadable reports.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        trends = st.session_state.trends

        with col1:
            excel_bytes = generate_excel_report(
                df_clean=df,
                exact_dups=st.session_state.exact_dups,
                possible_dups=st.session_state.possible_dups,
                anomaly_df=st.session_state.anomaly_df,
                recommendations=st.session_state.recommendations,
                trends=trends,
                currency=cur,
                session_name=st.session_state.filename or "analysis",
            )
            st.download_button("📊 Full Excel Report", data=excel_bytes,
                               file_name=f"expense_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

        with col2:
            dup_csv = generate_duplicate_csv(st.session_state.exact_dups, st.session_state.possible_dups)
            st.download_button("⚠️ Duplicate Report", data=dup_csv,
                               file_name="duplicate_payments.csv", mime="text/csv",
                               use_container_width=True)

        with col3:
            anomaly_csv = generate_anomaly_csv(st.session_state.anomaly_df)
            st.download_button("🔴 Anomaly Report", data=anomaly_csv,
                               file_name="anomaly_report.csv", mime="text/csv",
                               use_container_width=True)

        with col4:
            rec_csv = generate_recommendations_csv(st.session_state.recommendations, cur)
            st.download_button("💡 Recommendations", data=rec_csv,
                               file_name="savings_recommendations.csv", mime="text/csv",
                               use_container_width=True)

        # Clean transactions download
        clean_csv = df.copy()
        if "transaction_date" in clean_csv.columns:
            clean_csv["transaction_date"] = clean_csv["transaction_date"].dt.strftime("%Y-%m-%d")
        st.download_button("🧹 Cleaned Transactions (CSV)", data=clean_csv.to_csv(index=False).encode(),
                           file_name="cleaned_transactions.csv", mime="text/csv")

    st.divider()

    # ── Test Results ─────────────────────────────────────────────────────────
    st.subheader("Automated Test Suite")
    st.caption("Run the test suite with: `pytest tests/ -v`")

    test_results_path = os.path.join(ROOT_DIR, "test_results.txt")
    if os.path.exists(test_results_path):
        with open(test_results_path, "r") as f:
            results_text = f.read()
        st.code(results_text, language="text")
    else:
        st.info("No test results file found. Run tests with: `pytest tests/ -v > test_results.txt`")
        st.markdown("""
**To run tests:**
```bash
cd expense-savings-agent
pytest tests/ -v --tb=short
```

**Test coverage:**
- TC-01: Exact duplicate detection
- TC-02: Possible duplicate with date tolerance
- TC-03: Normal transaction not flagged
- TC-04: Unusually large transaction flagged
- TC-05: Missing/invalid amounts handled safely
- TC-06: Invalid date formats produce validation result
- TC-07: Monthly spending totals match expected values
- TC-08: Savings calculations use correct multipliers
- TC-09: Same saving not counted twice
- TC-10: Empty dataset does not crash
- TC-11: CSV upload works correctly
- TC-12: Excel upload works correctly
- TC-13: Recommendation status changes persist in SQLite
- TC-14: Exported reports contain expected columns
- TC-15: Rule-based assistant answers using actual results
""")

    # Analysis history
    st.divider()
    st.subheader("Analysis History")
    sessions = get_sessions(10)
    if sessions:
        sess_df = pd.DataFrame(sessions)
        st.dataframe(sess_df[["session_name", "filename", "accepted_rows", "total_amount",
                                "currency", "analysis_date"]].rename(columns={
            "session_name": "Session", "filename": "File",
            "accepted_rows": "Rows", "total_amount": "Total",
            "currency": "Currency", "analysis_date": "Date",
        }), use_container_width=True, hide_index=True)
    else:
        st.caption("No previous sessions found.")


def render_about():
    st.title("ℹ️ About the Agent")
    st.markdown("""
## AI Expense Leakage and Business Savings Agent

This application helps **small businesses and startups** identify financial leakage, unusual spending patterns, duplicate payments, and cost-saving opportunities — without requiring access to real bank accounts.

---

### How It Works

```
Upload CSV/Excel → Validate → Map Columns → Run Detection Engine → Generate Recommendations → Download Reports
```

---

### Detection Modules

| Module | Method | Trigger |
|--------|--------|---------|
| Exact Duplicate Detection | Payment reference matching | Identical references |
| Possible Duplicate Detection | Vendor + Amount + Date proximity | Same vendor, same amount, ≤3 days apart |
| Unusual Expense Detection | Z-score (σ > 2.5) + Isolation Forest | Statistical outliers |
| Spending Trend Analysis | Month-over-month change | ≥25% increase per category |
| Recurring Expense Detection | Multi-month vendor pattern | ≥2 months of same vendor |

---

### Savings Estimate Methodology

All savings figures are **projections** based on documented assumptions:

- Exact duplicates: 8% of at-risk amount / month (requires ~8% actual double payments)
- Anomalies: 5% recovery through review
- Spending spikes: 15% optimization of excess
- Subscriptions: 10% savings via renegotiation
- Vendor comparison: 8% savings through competitive sourcing

**Savings are never double-counted.** The de-duplication engine ensures each opportunity is listed once.

---

### Technology Stack

- **Frontend**: Streamlit
- **Data**: Pandas, NumPy
- **ML**: Scikit-learn (Isolation Forest)
- **Charts**: Plotly
- **Storage**: SQLite
- **Reports**: OpenPyXL (Excel), Pandas (CSV)
- **Optional LLM**: OpenAI / Google Gemini / Anthropic (via environment variables)

---

### Privacy and Security

- Uploaded files are processed in memory only
- No financial data is permanently stored unless explicitly exported
- API keys are loaded from environment variables only — never from the UI
- All findings are decision-support signals, not proof of fraud or financial advice

---

### Running the Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

---

### Disclaimer

> This tool provides decision-support signals, not financial, legal, or accounting advice. Always consult a qualified financial professional before acting on these insights. Duplicate flags require manual verification against source documents. Savings estimates are projections and should not be recorded as realized savings.
""")

    st.divider()
    st.subheader("Architecture Diagram")
    st.code("""
┌──────────────────────────────────────────────────────────────────┐
│                     Streamlit Web Application                     │
│  ┌──────────┐  ┌───────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Overview │  │Upload/Validate│  │  Analysis  │  │ Reports  │  │
│  │Dashboard │  │   Page        │  │   Pages    │  │  Page    │  │
│  └──────────┘  └───────────────┘  └────────────┘  └──────────┘  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │       Analysis Pipeline      │
              │  ┌──────────────────────┐    │
              │  │   Data Loader        │    │
              │  │   (CSV / Excel)      │    │
              │  └──────────┬───────────┘    │
              │             │                │
              │  ┌──────────▼───────────┐    │
              │  │   Validation Engine  │    │
              │  │   (date/amount/ID)   │    │
              │  └──────────┬───────────┘    │
              │             │                │
              │  ┌──────────▼──────────────────────────────┐  │
              │  │         Detection Modules                │  │
              │  │  ┌─────────────┐  ┌──────────────────┐  │  │
              │  │  │  Duplicate  │  │ Anomaly Detection │  │  │
              │  │  │  Detection  │  │ (Stats + IF Model)│  │  │
              │  │  └─────────────┘  └──────────────────┘  │  │
              │  │  ┌─────────────┐  ┌──────────────────┐  │  │
              │  │  │   Trend     │  │   Recurring       │  │  │
              │  │  │  Analysis   │  │   Detection       │  │  │
              │  │  └─────────────┘  └──────────────────┘  │  │
              │  └────────────────────────────┬─────────────┘  │
              │                               │                │
              │  ┌────────────────────────────▼─────────────┐  │
              │  │      Recommendation Engine               │  │
              │  │  (Deduped, prioritized, assumption-based)│  │
              │  └────────────────────────────┬─────────────┘  │
              │                               │                │
              │  ┌────────────────────────────▼─────────────┐  │
              │  │           SQLite Database                 │  │
              │  │  (sessions, decisions, thresholds, flags) │  │
              │  └────────────────────────────┬─────────────┘  │
              │                               │                │
              │  ┌────────────────────────────▼─────────────┐  │
              │  │    Report Generator (Excel / CSV)        │  │
              │  └──────────────────────────────────────────┘  │
              └─────────────────────────────────────────────────┘
    """, language="text")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    init_session()
    page = render_sidebar()

    if page == "Overview Dashboard":
        render_overview()
    elif page == "Upload Expenses":
        render_upload()
    elif page == "Transaction Analysis":
        render_transaction_analysis()
    elif page == "Anomaly Detection":
        render_anomaly_detection()
    elif page == "Savings Recommendations":
        render_recommendations()
    elif page == "Expense Assistant":
        render_assistant()
    elif page == "Reports & Test Results":
        render_reports()
    elif page == "About the Agent":
        render_about()


if __name__ == "__main__":
    main()
