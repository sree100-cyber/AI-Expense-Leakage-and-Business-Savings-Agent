"""
conftest.py - Shared fixtures for all test modules.
"""
import sys
import os
import pytest
import pandas as pd
from datetime import date, timedelta

# Make sure the project root is on the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def sample_df():
    """A small clean DataFrame with diverse test cases."""
    return pd.DataFrame({
        "transaction_id": ["TXN-001", "TXN-002", "TXN-003", "TXN-004", "TXN-005",
                           "TXN-006", "TXN-007", "TXN-008", "TXN-009", "TXN-010"],
        "transaction_date": pd.to_datetime([
            "2024-01-15", "2024-01-15", "2024-02-01", "2024-02-28",
            "2024-03-10", "2024-03-10", "2024-04-05", "2024-04-05",
            "2024-05-20", "2024-06-01",
        ]),
        "vendor": ["Vendor A", "Vendor A", "Vendor B", "Vendor C",
                   "Vendor D", "Vendor D", "Vendor E", "Vendor E",
                   "Vendor F", "Vendor G"],
        "expense_category": ["Software", "Software", "Marketing", "Travel",
                              "Legal", "Legal", "Office Supplies", "Office Supplies",
                              "Equipment", "Utilities"],
        "description": ["SaaS license", "SaaS license", "Ad campaign", "Flight NYC",
                         "Retainer", "Retainer", "Pens & paper", "Pens & paper",
                         "Server rack", "Internet"],
        "amount": [1200.00, 1200.00, 800.00, 350.00,
                   5000.00, 5000.00, 45.00, 45.00,
                   12000.00, 220.00],
        "payment_reference": ["REF-001", "REF-001", "REF-002", "REF-003",
                               "REF-004", "REF-005", "REF-006", "REF-007",
                               "REF-008", "REF-009"],
        "payment_method": ["Corporate Card"] * 10,
        "department": ["Engineering", "Engineering", "Marketing", "Sales",
                        "Finance", "Finance", "Operations", "Operations",
                        "Engineering", "Operations"],
    })


@pytest.fixture
def empty_df():
    """Empty DataFrame with canonical columns."""
    return pd.DataFrame(columns=[
        "transaction_id", "transaction_date", "vendor", "expense_category",
        "description", "amount", "payment_reference", "payment_method", "department"
    ])


@pytest.fixture
def minimal_df():
    """Minimal valid DataFrame with just date and amount."""
    return pd.DataFrame({
        "transaction_id": ["TXN-A", "TXN-B"],
        "transaction_date": pd.to_datetime(["2024-03-01", "2024-04-01"]),
        "vendor": ["Acme Corp", "Acme Corp"],
        "expense_category": ["Software", "Software"],
        "description": ["License fee", "License fee"],
        "amount": [500.0, 500.0],
        "payment_reference": ["R-A", "R-B"],
        "payment_method": ["Card", "Card"],
        "department": ["IT", "IT"],
    })
