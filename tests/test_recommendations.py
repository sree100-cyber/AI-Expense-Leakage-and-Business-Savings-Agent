"""
test_recommendations.py - Tests for the recommendation engine.
TC-07, TC-08, TC-09, TC-13
"""
import pytest
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.recommendation_engine import (
    generate_recommendations,
    compute_savings_totals,
    deduplicate_recommendations,
    recommendations_from_duplicates,
)
from modules.expense_trends import run_trend_analysis
from modules.database import init_db, upsert_recommendation, get_recommendations, update_recommendation_status


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_monthly_df():
    """DataFrame with 3 months of data, calculable monthly totals."""
    rows = []
    # Jan: Software=1000, Travel=500
    rows.extend([
        {"transaction_id": "T1", "transaction_date": pd.Timestamp("2024-01-15"),
         "vendor": "SaaS Co", "expense_category": "Software", "description": "SaaS",
         "amount": 1000.0, "payment_reference": "R1", "payment_method": "Card", "department": "Eng"},
        {"transaction_id": "T2", "transaction_date": pd.Timestamp("2024-01-20"),
         "vendor": "Airline A", "expense_category": "Travel", "description": "Flight",
         "amount": 500.0, "payment_reference": "R2", "payment_method": "Card", "department": "Sales"},
    ])
    # Feb: Software=1000, Travel=800
    rows.extend([
        {"transaction_id": "T3", "transaction_date": pd.Timestamp("2024-02-10"),
         "vendor": "SaaS Co", "expense_category": "Software", "description": "SaaS",
         "amount": 1000.0, "payment_reference": "R3", "payment_method": "Card", "department": "Eng"},
        {"transaction_id": "T4", "transaction_date": pd.Timestamp("2024-02-25"),
         "vendor": "Airline A", "expense_category": "Travel", "description": "Flight",
         "amount": 800.0, "payment_reference": "R4", "payment_method": "Card", "department": "Sales"},
    ])
    # Mar: Software=1000, Travel=2000 (spike)
    rows.extend([
        {"transaction_id": "T5", "transaction_date": pd.Timestamp("2024-03-05"),
         "vendor": "SaaS Co", "expense_category": "Software", "description": "SaaS",
         "amount": 1000.0, "payment_reference": "R5", "payment_method": "Card", "department": "Eng"},
        {"transaction_id": "T6", "transaction_date": pd.Timestamp("2024-03-20"),
         "vendor": "Airline A", "expense_category": "Travel", "description": "Conference travel",
         "amount": 2000.0, "payment_reference": "R6", "payment_method": "Card", "department": "Sales"},
    ])
    return pd.DataFrame(rows)


class TestMonthlyTotals:
    def test_monthly_software_total_correct(self):
        """TC-07: Monthly software total matches manually calculated value."""
        df = make_monthly_df()
        trends = run_trend_analysis(df)
        monthly_cat = trends["monthly_by_category"]
        software_monthly = monthly_cat[monthly_cat["expense_category"] == "Software"]
        # Each month should be 1000
        for _, row in software_monthly.iterrows():
            assert abs(row["amount"] - 1000.0) < 0.01, \
                f"Software monthly total should be 1000, got {row['amount']} for {row['year_month']}"

    def test_monthly_travel_jan(self):
        """January travel total == 500."""
        df = make_monthly_df()
        trends = run_trend_analysis(df)
        monthly_cat = trends["monthly_by_category"]
        jan_travel = monthly_cat[
            (monthly_cat["expense_category"] == "Travel") &
            (monthly_cat["year_month_str"] == "2024-01")
        ]
        assert not jan_travel.empty
        assert abs(jan_travel.iloc[0]["amount"] - 500.0) < 0.01

    def test_travel_spike_detected(self):
        """March travel spike from 800 to 2000 should be in spending_increases."""
        df = make_monthly_df()
        trends = run_trend_analysis(df)
        increases = trends["spending_increases"]
        travel_spikes = [i for i in increases if i["category"] == "Travel"]
        assert len(travel_spikes) >= 1, "Travel spike from Feb to Mar should be detected"
        mar_spike = [i for i in travel_spikes if i["current_month"] == "2024-03"]
        assert len(mar_spike) >= 1
        assert mar_spike[0]["pct_increase"] > 50


class TestSavingsCalculations:
    def test_annual_savings_is_monthly_times_12(self):
        """TC-08: Annual savings = monthly savings * 12."""
        recs = recommendations_from_duplicates(
            pd.DataFrame({
                "duplicate_group_id": ["EX-0001", "EX-0001"],
                "transaction_id": ["T1", "T2"],
                "transaction_date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "vendor": ["X", "X"],
                "amount": [1000.0, 1000.0],
                "match_reason": ["ref"] * 2,
                "confidence": ["High"] * 2,
                "duplicate_type": ["Exact"] * 2,
            }),
            pd.DataFrame()
        )
        for rec in recs:
            if rec.get("monthly_savings", 0) > 0:
                expected_annual = round(rec["monthly_savings"] * 12, 2)
                assert abs(rec["annual_savings"] - expected_annual) < 0.01, \
                    f"Annual savings {rec['annual_savings']} != monthly {rec['monthly_savings']} * 12"

    def test_no_double_counting(self):
        """TC-09: deduplicate_recommendations removes same (title, category) twice."""
        recs = [
            {"title": "Review Exact Duplicate Payments", "category": "Payment Controls",
             "monthly_savings": 100, "annual_savings": 1200},
            {"title": "Review Exact Duplicate Payments", "category": "Payment Controls",
             "monthly_savings": 100, "annual_savings": 1200},
            {"title": "Audit Recurring Subscription: SaaS Co", "category": "Subscriptions",
             "monthly_savings": 50, "annual_savings": 600},
        ]
        unique = deduplicate_recommendations(recs)
        assert len(unique) == 2, "Duplicate recommendation title+category should be removed"

    def test_savings_totals_sums_correctly(self):
        """compute_savings_totals sums monthly and annual correctly."""
        recs = [
            {"monthly_savings": 100, "annual_savings": 1200, "priority": "High", "status": "Pending"},
            {"monthly_savings": 50, "annual_savings": 600, "priority": "Medium", "status": "Accepted"},
            {"monthly_savings": 25, "annual_savings": 300, "priority": "Low", "status": "Implemented"},
        ]
        totals = compute_savings_totals(recs)
        assert abs(totals["estimated_monthly_savings"] - 175) < 0.01
        assert abs(totals["estimated_annual_savings"] - 2100) < 0.01
        assert abs(totals["accepted_monthly"] - 50) < 0.01
        assert abs(totals["implemented_monthly"] - 25) < 0.01


class TestDatabasePersistence:
    def test_recommendation_status_persists(self, tmp_path):
        """TC-13: Recommendation status changes persist in SQLite."""
        import modules.database as db
        # Use a temp DB for isolation
        original_path = db.DB_PATH
        db.DB_PATH = str(tmp_path / "test_agent.db")
        try:
            db.init_db()
            session_id = db.save_session("test.csv", 10, 9, 1, 5000.0)
            rec_id = db.upsert_recommendation(
                session_id, "Test Rec", "Software", "Pending", 100.0, 1200.0, "High"
            )
            # Change status to Accepted
            result = db.update_recommendation_status(rec_id, "Accepted", "Approved by manager")
            assert result, "Status update should return True"
            # Retrieve and verify
            recs = db.get_recommendations(session_id)
            assert len(recs) == 1
            assert recs[0]["status"] == "Accepted"
            assert recs[0]["notes"] == "Approved by manager"
        finally:
            db.DB_PATH = original_path

    def test_category_threshold_upsert(self, tmp_path):
        """Category thresholds persist and can be updated."""
        import modules.database as db
        original_path = db.DB_PATH
        db.DB_PATH = str(tmp_path / "test_thresholds.db")
        try:
            db.init_db()
            db.upsert_category_threshold("Software", 5000.0, 20.0)
            thresholds = db.get_category_thresholds()
            assert "Software" in thresholds
            assert abs(thresholds["Software"]["monthly_threshold"] - 5000.0) < 0.01
            # Update
            db.upsert_category_threshold("Software", 6000.0, 25.0)
            thresholds2 = db.get_category_thresholds()
            assert abs(thresholds2["Software"]["monthly_threshold"] - 6000.0) < 0.01
        finally:
            db.DB_PATH = original_path
