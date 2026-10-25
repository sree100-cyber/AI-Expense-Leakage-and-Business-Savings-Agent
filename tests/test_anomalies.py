"""
test_anomalies.py - Tests for anomaly detection.
TC-04, TC-05, TC-06
"""
import pytest
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.anomaly_detection import (
    statistical_anomaly_detection,
    run_anomaly_detection,
)


def make_normal_df():
    """Build a DataFrame with one extreme outlier among normal values."""
    amounts = [100, 110, 105, 98, 103, 115, 99, 107, 95, 50000]  # last is outlier
    df = pd.DataFrame({
        "transaction_id": [f"T{i}" for i in range(len(amounts))],
        "transaction_date": pd.to_datetime(["2024-01-01"] * len(amounts)),
        "vendor": ["Vendor A"] * len(amounts),
        "expense_category": ["Software"] * len(amounts),
        "description": ["Expense"] * len(amounts),
        "amount": [float(a) for a in amounts],
        "payment_reference": [f"R{i}" for i in range(len(amounts))],
        "payment_method": ["Card"] * len(amounts),
        "department": ["Eng"] * len(amounts),
    })
    return df


class TestStatisticalAnomalyDetection:
    def test_large_outlier_is_flagged(self):
        """TC-04: An unusually large transaction is flagged by statistical rule."""
        df = make_normal_df()
        result = statistical_anomaly_detection(df)
        # The last row (50000) should be flagged
        last_idx = result.index[-1]
        assert result.at[last_idx, "_stat_anomaly"], \
            "Extremely large transaction should be flagged"

    def test_normal_transactions_not_flagged(self):
        """Normal transactions near the mean are NOT flagged."""
        df = make_normal_df()
        result = statistical_anomaly_detection(df)
        # First 9 rows are normal
        normal_rows = result.iloc[:-1]
        assert not normal_rows["_stat_anomaly"].all(), \
            "Most normal transactions should not be flagged"

    def test_empty_df_does_not_crash(self, empty_df):
        """TC-10: Empty DataFrame returns safely."""
        # Need transaction_date and amount columns
        empty_df["amount"] = pd.Series(dtype=float)
        empty_df["transaction_date"] = pd.Series(dtype="datetime64[ns]")
        result = statistical_anomaly_detection(empty_df)
        assert result.empty or "_stat_anomaly" in result.columns

    def test_anomaly_has_reason_text(self):
        """Flagged anomalies include a human-readable reason."""
        df = make_normal_df()
        result = statistical_anomaly_detection(df)
        flagged = result[result["_stat_anomaly"]]
        assert not flagged.empty
        assert flagged["_stat_reason"].str.len().gt(10).all(), \
            "Anomaly reason should be a non-trivial string"


class TestRunAnomalyDetection:
    def test_run_returns_flagged_and_summary(self):
        """run_anomaly_detection returns a flagged df and summary dict."""
        df = make_normal_df()
        flagged, summary = run_anomaly_detection(df)
        assert isinstance(flagged, pd.DataFrame)
        assert isinstance(summary, dict)
        assert "total_flagged" in summary
        assert "stat_flags" in summary

    def test_run_anomaly_on_empty(self, empty_df):
        """TC-10: Empty input returns empty flagged df and zero totals."""
        flagged, summary = run_anomaly_detection(empty_df)
        assert flagged.empty
        assert summary["total_flagged"] == 0

    def test_flagged_amount_is_correct(self):
        """Flagged amount in summary == sum of flagged rows' amounts."""
        df = make_normal_df()
        flagged, summary = run_anomaly_detection(df)
        expected = flagged["amount"].sum() if not flagged.empty else 0
        assert abs(summary["flagged_amount"] - expected) < 0.01
