"""
test_data_validation.py - Tests for upload validation.
TC-05, TC-06, TC-11, TC-12
"""
import pytest
import pandas as pd
import numpy as np
import io
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.validation import validate_transactions, validation_summary
from modules.data_loader import load_dataframe, map_and_normalize


class TestAmountValidation:
    def test_missing_amount_is_rejected(self):
        """TC-05: Row with missing amount is rejected."""
        df = pd.DataFrame({
            "transaction_id": ["T1", "T2"],
            "transaction_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "vendor": ["A", "B"],
            "expense_category": ["Software", "Software"],
            "description": ["x", "y"],
            "amount": [100.0, np.nan],
            "payment_reference": ["R1", "R2"],
            "payment_method": ["Card", "Card"],
            "department": ["Eng", "Eng"],
        })
        clean, rejected, warnings = validate_transactions(df)
        assert len(rejected) == 1, "Row with NaN amount should be rejected"
        assert len(clean) == 1

    def test_invalid_string_amount_is_rejected(self):
        """TC-05: Row with non-numeric amount string is rejected."""
        df = pd.DataFrame({
            "transaction_id": ["T1"],
            "transaction_date": ["2024-01-01"],
            "vendor": ["A"],
            "expense_category": ["Software"],
            "description": ["x"],
            "amount": ["INVALID"],
            "payment_reference": ["R1"],
            "payment_method": ["Card"],
            "department": ["Eng"],
        })
        clean, rejected, warnings = validate_transactions(df)
        assert len(rejected) == 1

    def test_negative_amount_is_rejected(self):
        """Negative amounts are rejected."""
        df = pd.DataFrame({
            "transaction_id": ["T1"],
            "transaction_date": ["2024-01-01"],
            "vendor": ["A"],
            "expense_category": ["Software"],
            "description": ["x"],
            "amount": [-500.0],
            "payment_reference": ["R1"],
            "payment_method": ["Card"],
            "department": ["Eng"],
        })
        clean, rejected, _ = validate_transactions(df)
        assert len(rejected) == 1

    def test_valid_amount_is_accepted(self):
        """A normal numeric amount passes validation."""
        df = pd.DataFrame({
            "transaction_id": ["T1"],
            "transaction_date": ["2024-01-01"],
            "vendor": ["A"],
            "expense_category": ["Software"],
            "description": ["x"],
            "amount": [299.99],
            "payment_reference": ["R1"],
            "payment_method": ["Card"],
            "department": ["Eng"],
        })
        clean, rejected, _ = validate_transactions(df)
        assert len(clean) == 1
        assert len(rejected) == 0


class TestDateValidation:
    def test_invalid_date_format_is_rejected(self):
        """TC-06: Invalid date string produces a clear rejection."""
        df = pd.DataFrame({
            "transaction_id": ["T1"],
            "transaction_date": ["NOT_A_DATE"],
            "vendor": ["A"],
            "expense_category": ["Software"],
            "description": ["x"],
            "amount": [100.0],
            "payment_reference": ["R1"],
            "payment_method": ["Card"],
            "department": ["Eng"],
        })
        clean, rejected, warnings = validate_transactions(df)
        assert len(rejected) == 1, "Invalid date should cause rejection"

    def test_various_valid_date_formats_accepted(self):
        """Multiple date formats are parsed correctly."""
        df = pd.DataFrame({
            "transaction_id": ["T1", "T2", "T3"],
            "transaction_date": ["2024-01-15", "15/01/2024", "Jan 15 2024"],
            "vendor": ["A", "B", "C"],
            "expense_category": ["Software", "Marketing", "Travel"],
            "description": ["x", "y", "z"],
            "amount": [100.0, 200.0, 300.0],
            "payment_reference": ["R1", "R2", "R3"],
            "payment_method": ["Card", "Card", "Card"],
            "department": ["Eng", "Mkt", "Sales"],
        })
        clean, rejected, warnings = validate_transactions(df)
        assert len(clean) >= 2, "Most common date formats should be accepted"


class TestCSVUpload:
    def test_csv_upload_works(self, tmp_path):
        """TC-11: CSV file loads correctly into a DataFrame."""
        csv_content = (
            "transaction_id,transaction_date,vendor,expense_category,"
            "description,amount,payment_reference,payment_method,department\n"
            "T1,2024-01-15,Vendor A,Software,License,1200.00,REF-001,Card,Eng\n"
            "T2,2024-02-10,Vendor B,Marketing,Campaign,800.00,REF-002,Card,Mkt\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        with open(csv_file, "rb") as f:
            df, err = load_dataframe(f, "test.csv")
        assert err == "", f"CSV load error: {err}"
        assert df is not None
        assert len(df) == 2

    def test_csv_with_column_mapping(self, tmp_path):
        """Differently-named columns are correctly mapped."""
        csv_content = (
            "id,date,supplier,category,memo,total,ref,method,dept\n"
            "001,2024-03-01,Acme Corp,Software,Annual license,2400.00,INV-001,Wire,IT\n"
        )
        csv_file = tmp_path / "mapped.csv"
        csv_file.write_text(csv_content, encoding="utf-8")
        with open(csv_file, "rb") as f:
            df, err = load_dataframe(f, "mapped.csv")
        assert df is not None
        mapped_df, mapping = map_and_normalize(df)
        # Should detect at least some key columns
        assert "amount" in mapped_df.columns
        assert "transaction_date" in mapped_df.columns


class TestExcelUpload:
    def test_excel_upload_works(self, tmp_path):
        """TC-12: Excel file loads correctly into a DataFrame."""
        data = pd.DataFrame({
            "transaction_id": ["T1", "T2"],
            "transaction_date": ["2024-01-15", "2024-02-10"],
            "vendor": ["Vendor A", "Vendor B"],
            "expense_category": ["Software", "Marketing"],
            "description": ["License", "Campaign"],
            "amount": [1200.00, 800.00],
            "payment_reference": ["REF-001", "REF-002"],
            "payment_method": ["Card", "Card"],
            "department": ["Eng", "Mkt"],
        })
        excel_file = tmp_path / "test.xlsx"
        data.to_excel(excel_file, index=False)

        with open(excel_file, "rb") as f:
            df, err = load_dataframe(f, "test.xlsx")
        assert err == "", f"Excel load error: {err}"
        assert df is not None
        assert len(df) == 2


class TestEmptyAndEdgeCases:
    def test_empty_file_returns_error(self):
        """Empty file content handled gracefully."""
        buf = io.StringIO("")
        df, err = load_dataframe(buf, "empty.csv")
        # Either returns an error or empty DataFrame — should not crash
        assert df is None or (df is not None and df.empty) or err != ""

    def test_validation_summary_correct(self):
        """validation_summary returns correct acceptance rate."""
        clean = pd.DataFrame({"transaction_date": pd.to_datetime(["2024-01-01"]), "amount": [100.0]})
        rejected = pd.DataFrame({"transaction_date": pd.to_datetime(["2024-01-02"]), "amount": [np.nan]})
        summary = validation_summary(2, clean, rejected, [])
        assert summary["accepted"] == 1
        assert summary["rejected"] == 1
        assert summary["acceptance_rate"] == 50.0
