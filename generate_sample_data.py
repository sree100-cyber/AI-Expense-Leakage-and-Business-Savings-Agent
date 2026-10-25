"""
generate_sample_data.py
Generates synthetic sample expense data for demonstration.
Run: python generate_sample_data.py
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
import random
import sys
import os

# Ensure output goes to data/ folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "sample_expenses.csv")

random.seed(42)
np.random.seed(42)

VENDORS = {
    "Software": ["Salesforce Inc.", "Microsoft Corp.", "Adobe Systems", "Zoom Video", "Slack Technologies",
                 "AWS Services", "Google Workspace", "HubSpot", "Notion", "Figma"],
    "Office Supplies": ["Staples", "Office Depot", "Amazon Business", "Uline", "W.B. Mason"],
    "Travel": ["Delta Airlines", "United Airlines", "Marriott Hotels", "Hilton Hotels",
               "Uber Business", "Lyft Business", "Hertz Rental", "American Airlines"],
    "Marketing": ["Facebook Ads", "Google Ads", "LinkedIn Ads", "Mailchimp", "Canva Pro"],
    "Legal & Professional": ["Baker McKenzie LLP", "Deloitte Advisory", "PwC Consulting",
                              "Local Law Firm", "KPMG Services"],
    "Utilities": ["AT&T Business", "Comcast Business", "WeWork Coworking",
                  "Con Edison", "Verizon Business"],
    "Catering & Meals": ["DoorDash for Work", "Grubhub Business", "Local Catering Co.",
                          "Starbucks Corporate", "Restaurant Express"],
    "Equipment": ["Dell Technologies", "Apple Business", "HP Inc.", "Logitech",
                  "Canon Business"],
}

DEPARTMENTS = ["Engineering", "Marketing", "Sales", "Finance", "Operations", "HR", "Product"]

PAYMENT_METHODS = ["Corporate Card", "Bank Transfer", "Check", "ACH", "Wire Transfer"]

# Base amounts per category
CATEGORY_BASE_AMOUNTS = {
    "Software": (200, 5000),
    "Office Supplies": (50, 800),
    "Travel": (300, 3000),
    "Marketing": (500, 8000),
    "Legal & Professional": (1500, 15000),
    "Utilities": (200, 2000),
    "Catering & Meals": (80, 600),
    "Equipment": (400, 4000),
}

START_DATE = date(2024, 1, 1)
END_DATE = date(2024, 12, 31)


def random_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def generate_ref():
    prefixes = ["INV", "REF", "CHK", "PO", "ACH"]
    return f"{random.choice(prefixes)}-{random.randint(10000, 99999)}"


records = []
rec_id = 1

# ── Normal transactions ───────────────────────────────────────────────────────
for _ in range(80):
    cat = random.choice(list(VENDORS.keys()))
    vendor = random.choice(VENDORS[cat])
    lo, hi = CATEGORY_BASE_AMOUNTS[cat]
    amount = round(random.uniform(lo, hi), 2)
    txn_date = random_date(START_DATE, END_DATE)
    records.append({
        "transaction_id": f"TXN-{rec_id:05d}",
        "transaction_date": txn_date.strftime("%Y-%m-%d"),
        "vendor": vendor,
        "expense_category": cat,
        "description": f"{cat} expense - {vendor}",
        "amount": amount,
        "payment_reference": generate_ref(),
        "payment_method": random.choice(PAYMENT_METHODS),
        "department": random.choice(DEPARTMENTS),
        "note": "Normal",
    })
    rec_id += 1

# ── Recurring subscriptions (Salesforce, Microsoft, Zoom) ────────────────────
for month in range(1, 13):
    for sub_vendor, sub_amt in [
        ("Salesforce Inc.", 1200.00),
        ("Microsoft Corp.", 450.00),
        ("Zoom Video", 199.00),
        ("Google Workspace", 299.00),
    ]:
        day = random.randint(1, 5)
        txn_date = date(2024, month, day)
        records.append({
            "transaction_id": f"TXN-{rec_id:05d}",
            "transaction_date": txn_date.strftime("%Y-%m-%d"),
            "vendor": sub_vendor,
            "expense_category": "Software",
            "description": f"Monthly subscription - {sub_vendor}",
            "amount": sub_amt,
            "payment_reference": f"SUB-{sub_vendor[:3].upper()}-2024-{month:02d}",
            "payment_method": "Corporate Card",
            "department": "Engineering",
            "note": "Recurring Subscription",
        })
        rec_id += 1

# ── Exact duplicate payment (same payment reference) ─────────────────────────
dup_ref = "INV-77777"
dup_date = date(2024, 3, 15)
for i in range(2):
    records.append({
        "transaction_id": f"TXN-{rec_id:05d}",
        "transaction_date": dup_date.strftime("%Y-%m-%d"),
        "vendor": "Baker McKenzie LLP",
        "expense_category": "Legal & Professional",
        "description": "Legal retainer Q1 2024",
        "amount": 7500.00,
        "payment_reference": dup_ref,
        "payment_method": "Bank Transfer",
        "department": "Finance",
        "note": "SYNTHETIC: Exact Duplicate Payment",
    })
    rec_id += 1

# ── Possible duplicate (same vendor+amount, 2 days apart) ────────────────────
for day_offset in [0, 2]:
    records.append({
        "transaction_id": f"TXN-{rec_id:05d}",
        "transaction_date": (date(2024, 6, 10) + timedelta(days=day_offset)).strftime("%Y-%m-%d"),
        "vendor": "Deloitte Advisory",
        "expense_category": "Legal & Professional",
        "description": "Consulting services June",
        "amount": 4250.00,
        "payment_reference": f"DLTE-{20240610 + day_offset}",
        "payment_method": "Wire Transfer",
        "department": "Finance",
        "note": "SYNTHETIC: Possible Duplicate",
    })
    rec_id += 1

# ── Unusually large expense ───────────────────────────────────────────────────
records.append({
    "transaction_id": f"TXN-{rec_id:05d}",
    "transaction_date": date(2024, 8, 20).strftime("%Y-%m-%d"),
    "vendor": "Dell Technologies",
    "expense_category": "Equipment",
    "description": "Bulk laptop procurement Q3",
    "amount": 85000.00,
    "payment_reference": "PO-DELL-Q3-2024",
    "payment_method": "Bank Transfer",
    "department": "Engineering",
    "note": "SYNTHETIC: Unusual Large Expense",
})
rec_id += 1

# ── Spending spike in Marketing (Sept → Oct) ──────────────────────────────────
for month, mult in [(9, 1.0), (10, 2.8)]:
    records.append({
        "transaction_id": f"TXN-{rec_id:05d}",
        "transaction_date": date(2024, month, 5).strftime("%Y-%m-%d"),
        "vendor": "Facebook Ads",
        "expense_category": "Marketing",
        "description": f"Campaign spend - Month {month}",
        "amount": round(5000.00 * mult, 2),
        "payment_reference": f"FB-ADS-2024-{month:02d}",
        "payment_method": "Corporate Card",
        "department": "Marketing",
        "note": f"SYNTHETIC: Marketing spike (mult={mult})",
    })
    rec_id += 1

for month, mult in [(9, 1.0), (10, 3.0)]:
    records.append({
        "transaction_id": f"TXN-{rec_id:05d}",
        "transaction_date": date(2024, month, 8).strftime("%Y-%m-%d"),
        "vendor": "Google Ads",
        "expense_category": "Marketing",
        "description": f"PPC campaign - Month {month}",
        "amount": round(3500.00 * mult, 2),
        "payment_reference": f"GADS-2024-{month:02d}",
        "payment_method": "Corporate Card",
        "department": "Marketing",
        "note": f"SYNTHETIC: Marketing spike (mult={mult})",
    })
    rec_id += 1

# ── Normal (must not be flagged) ─────────────────────────────────────────────
for _ in range(20):
    cat = random.choice(["Office Supplies", "Catering & Meals", "Utilities"])
    vendor = random.choice(VENDORS[cat])
    lo, hi = CATEGORY_BASE_AMOUNTS[cat]
    amount = round(random.uniform(lo * 0.8, hi * 0.8), 2)
    txn_date = random_date(START_DATE, END_DATE)
    records.append({
        "transaction_id": f"TXN-{rec_id:05d}",
        "transaction_date": txn_date.strftime("%Y-%m-%d"),
        "vendor": vendor,
        "expense_category": cat,
        "description": f"{cat} - routine",
        "amount": amount,
        "payment_reference": generate_ref(),
        "payment_method": random.choice(PAYMENT_METHODS),
        "department": random.choice(DEPARTMENTS),
        "note": "Normal (should not flag)",
    })
    rec_id += 1

# ── Build and save ────────────────────────────────────────────────────────────
df = pd.DataFrame(records)
df = df.sort_values("transaction_date").reset_index(drop=True)

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)
print(f"[OK] Generated {len(df)} synthetic transactions -> {OUTPUT_PATH}")
print(f"   Columns: {list(df.columns)}")
print(f"   Date range: {df['transaction_date'].min()} to {df['transaction_date'].max()}")
print(f"   Total amount: ${df['amount'].sum():,.2f}")
