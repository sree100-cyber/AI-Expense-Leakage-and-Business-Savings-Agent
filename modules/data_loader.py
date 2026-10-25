"""
data_loader.py - Load and map transaction data from CSV/Excel uploads
"""
import pandas as pd
import numpy as np
import io
from typing import Tuple, Optional


# Canonical column names used throughout the application
CANONICAL_COLUMNS = [
    "transaction_id",
    "transaction_date",
    "vendor",
    "expense_category",
    "description",
    "amount",
    "payment_reference",
    "payment_method",
    "department",
]

# Flexible aliases that map to canonical names
COLUMN_ALIASES = {
    "transaction_id": ["txn_id", "trans_id", "id", "transaction id", "txn id", "trans id", "transaction_number", "txn_no"],
    "transaction_date": ["date", "txn_date", "trans_date", "transaction date", "invoice_date", "payment_date", "trans date", "posting_date"],
    "vendor": ["vendor_name", "supplier", "merchant", "payee", "vendor name", "supplier_name", "company"],
    "expense_category": ["category", "expense_type", "type", "cost_category", "expense category", "category_name", "account"],
    "description": ["memo", "details", "notes", "narrative", "particulars", "remarks", "line_item"],
    "amount": ["total", "total_amount", "transaction_amount", "value", "cost", "expense_amount", "debit", "amount_usd"],
    "payment_reference": ["ref", "reference", "payment_ref", "invoice_ref", "check_number", "payment reference", "ref_no", "invoice_number"],
    "payment_method": ["method", "payment_type", "pay_method", "mode", "payment method", "pay_type"],
    "department": ["dept", "division", "business_unit", "team", "cost_center", "department_name", "dept_name"],
}


def _detect_column_mapping(df: pd.DataFrame) -> dict:
    """
    Auto-detect which uploaded columns correspond to canonical columns.
    Returns {canonical_name: uploaded_col_name} for matches found.
    """
    mapping = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}

    for canonical, aliases in COLUMN_ALIASES.items():
        # Direct match
        if canonical in lower_cols:
            mapping[canonical] = lower_cols[canonical]
            continue
        # Alias match
        for alias in aliases:
            if alias in lower_cols:
                mapping[canonical] = lower_cols[alias]
                break

    return mapping


def load_dataframe(file_obj, filename: str) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Load a CSV or Excel file and return (DataFrame, error_message).
    Returns (None, error) on failure.
    """
    try:
        if filename.lower().endswith(".csv"):
            # Try common encodings
            for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                try:
                    if hasattr(file_obj, "seek"):
                        file_obj.seek(0)
                    df = pd.read_csv(file_obj, encoding=enc, low_memory=False)
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            else:
                return None, "Could not decode CSV file. Ensure it is UTF-8 or Latin-1 encoded."
        elif filename.lower().endswith((".xlsx", ".xls")):
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            df = pd.read_excel(file_obj, engine="openpyxl" if filename.endswith(".xlsx") else "xlrd")
        else:
            return None, f"Unsupported file type: {filename}. Upload a .csv or .xlsx file."

        if df.empty:
            return None, "The uploaded file is empty."

        return df, ""
    except Exception as e:
        return None, f"File loading error: {e}"


def map_and_normalize(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Map uploaded columns to canonical names and normalize data types.
    Returns (normalized_df, mapping_report).
    """
    mapping = _detect_column_mapping(df)

    # Rename matched columns to canonical names
    rename_dict = {v: k for k, v in mapping.items()}
    df = df.rename(columns=rename_dict)

    # Add missing canonical columns as NaN
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    # Keep only canonical columns plus any extras
    extra_cols = [c for c in df.columns if c not in CANONICAL_COLUMNS]
    df = df[CANONICAL_COLUMNS + extra_cols]

    return df, mapping


def generate_transaction_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Generate synthetic transaction IDs for rows missing them."""
    mask = df["transaction_id"].isna() | (df["transaction_id"].astype(str).str.strip() == "")
    if mask.any():
        count = mask.sum()
        start = 1
        df.loc[mask, "transaction_id"] = [f"AUTO-{i:05d}" for i in range(start, start + count)]
    return df
