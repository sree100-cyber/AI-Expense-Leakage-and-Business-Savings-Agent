"""
test_duplicates.py - Tests for duplicate payment detection.
TC-01, TC-02, TC-03
"""
import pytest
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.duplicate_detection import (
    detect_exact_duplicates,
    detect_possible_duplicates,
    run_duplicate_detection,
)


class TestExactDuplicates:
    def test_exact_duplicate_detected(self, sample_df):
        """TC-01: Exact duplicate (same payment ref) is detected."""
        # sample_df has TXN-001 and TXN-002 both with REF-001
        result = detect_exact_duplicates(sample_df)
        assert not result.empty, "Exact duplicates should be detected"
        assert result["duplicate_group_id"].nunique() >= 1
        assert "REF-001" in result["match_reason"].values[0]

    def test_exact_duplicate_group_contains_both_rows(self, sample_df):
        """Both rows sharing a reference appear in the same group."""
        result = detect_exact_duplicates(sample_df)
        ref_group = result[result["match_reason"].str.contains("REF-001")]
        assert len(ref_group) == 2

    def test_exact_duplicate_confidence_is_high(self, sample_df):
        """Exact duplicates should have High confidence."""
        result = detect_exact_duplicates(sample_df)
        assert (result["confidence"] == "High").all()

    def test_no_false_positive_unique_references(self):
        """TC-03: Unique references are NOT flagged as duplicates."""
        df = pd.DataFrame({
            "transaction_id": ["T1", "T2", "T3"],
            "transaction_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "vendor": ["A", "B", "C"],
            "expense_category": ["Software", "Marketing", "Travel"],
            "description": ["x", "y", "z"],
            "amount": [100.0, 200.0, 300.0],
            "payment_reference": ["REF-AAA", "REF-BBB", "REF-CCC"],
            "payment_method": ["Card", "Card", "Card"],
            "department": ["Eng", "Mkt", "Sales"],
        })
        result = detect_exact_duplicates(df)
        assert result.empty, "No duplicates should be found for unique references"

    def test_empty_df_returns_empty(self, empty_df):
        """Empty DataFrame returns empty result without error."""
        result = detect_exact_duplicates(empty_df)
        assert result.empty


class TestPossibleDuplicates:
    def test_possible_duplicate_same_vendor_amount_close_dates(self):
        """TC-02: Same vendor, same amount, dates within tolerance → flagged."""
        df = pd.DataFrame({
            "transaction_id": ["T1", "T2"],
            "transaction_date": pd.to_datetime(["2024-03-10", "2024-03-12"]),
            "vendor": ["Vendor X", "Vendor X"],
            "expense_category": ["Legal", "Legal"],
            "description": ["Invoice A", "Invoice B"],
            "amount": [3000.0, 3000.0],
            "payment_reference": ["REF-X1", "REF-X2"],
            "payment_method": ["Wire", "Wire"],
            "department": ["Finance", "Finance"],
        })
        result = detect_possible_duplicates(df, date_tolerance_days=3)
        assert not result.empty, "Possible duplicate should be detected"
        assert len(result) == 2

    def test_different_vendors_not_flagged(self):
        """Different vendors with same amount and date are NOT flagged."""
        df = pd.DataFrame({
            "transaction_id": ["T1", "T2"],
            "transaction_date": pd.to_datetime(["2024-03-10", "2024-03-10"]),
            "vendor": ["Vendor A", "Vendor B"],
            "expense_category": ["Software", "Software"],
            "description": ["Invoice A", "Invoice B"],
            "amount": [1000.0, 1000.0],
            "payment_reference": ["R1", "R2"],
            "payment_method": ["Card", "Card"],
            "department": ["Eng", "Eng"],
        })
        result = detect_possible_duplicates(df, date_tolerance_days=3)
        assert result.empty

    def test_same_vendor_far_apart_dates_not_flagged(self):
        """Same vendor and amount but 30 days apart: NOT flagged with default tolerance."""
        df = pd.DataFrame({
            "transaction_id": ["T1", "T2"],
            "transaction_date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "vendor": ["Vendor Z", "Vendor Z"],
            "expense_category": ["Software", "Software"],
            "description": ["Invoice", "Invoice"],
            "amount": [500.0, 500.0],
            "payment_reference": ["R1", "R2"],
            "payment_method": ["Card", "Card"],
            "department": ["IT", "IT"],
        })
        result = detect_possible_duplicates(df, date_tolerance_days=3)
        assert result.empty, "Transactions 30 days apart should not be flagged as possible duplicates"

    def test_run_duplicate_detection_summary(self, sample_df):
        """run_duplicate_detection returns non-empty summary with correct keys."""
        exact, possible, summary = run_duplicate_detection(sample_df)
        assert "exact_duplicate_groups" in summary
        assert "possible_duplicate_groups" in summary
        assert "total_at_risk_amount" in summary
        assert summary["exact_duplicate_groups"] >= 1
