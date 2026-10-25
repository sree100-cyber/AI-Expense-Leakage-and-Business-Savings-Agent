# AI Expense Leakage and Business Savings Agent

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red)](https://streamlit.io)
[![Tests](https://img.shields.io/badge/Tests-49%20Passed-brightgreen)](#test-results)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)

An AI-powered business expense analysis system that identifies financial leakage, unusual spending, duplicate payments, recurring expenses, and cost-saving opportunities — without requiring real bank account access.

---

## Features

| Feature | Description |
|---------|-------------|
| **Duplicate Detection** | Exact (payment reference) + possible (vendor + amount + date proximity) |
| **Anomaly Detection** | Z-score statistical analysis + Isolation Forest ML model |
| **Trend Analysis** | Month-over-month category spending, spike detection (≥25%) |
| **Recurring Expenses** | Subscription pattern recognition across multiple months |
| **Savings Recommendations** | Prioritized, evidence-based, assumption-transparent |
| **Expense Assistant** | Rule-based Q&A chatbot + optional LLM integration |
| **Interactive Reports** | Excel workbook (8 sheets) + CSV downloads |
| **SQLite Persistence** | Sessions, decisions, thresholds, flagged transactions |
| **49 Automated Tests** | Full pytest suite covering all 15 required test cases |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/sree100-cyber/AI-Expense-Leakage-and-Business-Savings-Agent.git
cd AI-Expense-Leakage-and-Business-Savings-Agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Generate sample data (if not present)

```bash
python generate_sample_data.py
```

### 4. Run the application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Click **"Load Sample Dataset"** on the Overview page to instantly see a full demo.

---

## Project Structure

```
expense-savings-agent/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── generate_sample_data.py     # Synthetic data generator
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore rules
├── test_results.txt            # Latest pytest output
├── README.md
│
├── modules/
│   ├── __init__.py
│   ├── database.py             # SQLite persistence layer
│   ├── data_loader.py          # CSV/Excel loading & column mapping
│   ├── validation.py           # Data validation & cleaning
│   ├── duplicate_detection.py  # Exact + possible duplicate detection
│   ├── anomaly_detection.py    # Statistical + Isolation Forest
│   ├── expense_trends.py       # Monthly trends & recurring detection
│   ├── recommendation_engine.py# Savings recommendation generation
│   ├── conversational_agent.py # Rule-based Q&A + LLM wrapper
│   └── report_generator.py     # Excel + CSV report generation
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared test fixtures
│   ├── test_duplicates.py      # TC-01, TC-02, TC-03
│   ├── test_anomalies.py       # TC-04, TC-05, TC-06, TC-10
│   ├── test_recommendations.py # TC-07, TC-08, TC-09, TC-13
│   ├── test_data_validation.py # TC-05, TC-06, TC-11, TC-12
│   └── test_reports.py         # TC-14, TC-15
│
├── data/
│   └── sample_expenses.csv     # 157 synthetic transactions (2024)
│
└── .streamlit/
    └── config.toml             # Theme configuration
```

---

## Application Pages

1. **Overview Dashboard** — KPI cards, trend chart, category pie, vendor bar, anomaly distribution, savings potential
2. **Upload Expenses** — CSV/Excel upload with column auto-mapping, validation summary, error display
3. **Transaction Analysis** — Filterable transaction table, monthly category breakdown, spending spike alerts
4. **Anomaly Detection** — Duplicate payment groups, unusual transaction list, amount distribution chart, ML details
5. **Savings Recommendations** — Prioritized cards with status management (Pending/Accepted/Rejected/Implemented)
6. **Expense Assistant** — Conversational Q&A using real analysis results, suggested questions
7. **Reports & Test Results** — Full Excel workbook + individual CSV downloads, test output display
8. **About the Agent** — Architecture diagram, methodology, disclaimers

---

## Detection Algorithms

### Duplicate Detection
- **Exact**: Transactions sharing an identical `payment_reference` (non-null)
- **Possible**: Same vendor + same amount within `date_tolerance_days` (default 3 days)

### Anomaly Detection
- **Statistical**: Z-score > 2.5 globally, per-category, and per-vendor
- **ML**: Isolation Forest (`contamination=0.05`, `n_estimators=200`) on amount + encoded categoricals
- Minimum 20 rows required to activate the ML model; degrades gracefully to statistical-only

### Trend Analysis
- Monthly per-category totals using `pd.Period("M")`
- Spike threshold: ≥25% month-over-month increase

### Recurring Expense Detection
- Vendors appearing in ≥2 distinct calendar months
- Coefficient of variation < 0.15 → "Consistent (subscription-like)"

---

## Savings Methodology

| Source | Discount Rate | Confidence |
|--------|--------------|------------|
| Exact duplicates | 8% of at-risk per month | High |
| Possible duplicates | 4% of at-risk per month | Medium |
| Top 5 anomalies | 5% of flagged amount | Medium |
| Spending spikes | 15% of excess above trend | Medium |
| Subscriptions | 10% of monthly cost | Low |
| Vendor comparison | 8% of recurring vendor spend | Low |

All savings are **projected estimates**, de-duplicated, and clearly labeled with their underlying assumptions.

---

## Optional LLM Integration

Copy `.env.example` to `.env` and set your API key:

```bash
# For OpenAI (GPT-4o-mini)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# For Google Gemini
LLM_PROVIDER=google
GOOGLE_API_KEY=AIza...

# For Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

The app works fully without an LLM key — the rule-based assistant covers all supported question patterns.

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v --tb=short

# Save results to file
pytest tests/ -v --tb=short > test_results.txt

# Run a specific test file
pytest tests/test_duplicates.py -v
```

### Test Coverage (49 tests)

| File | Tests | TC Coverage |
|------|-------|-------------|
| `test_duplicates.py` | 9 | TC-01, TC-02, TC-03 |
| `test_anomalies.py` | 7 | TC-04, TC-10 |
| `test_data_validation.py` | 11 | TC-05, TC-06, TC-11, TC-12 |
| `test_recommendations.py` | 14 | TC-07, TC-08, TC-09, TC-13 |
| `test_reports.py` | 8 | TC-14, TC-15 |

---

## Deployment to Streamlit Community Cloud

1. Push to a public GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account
4. Select `app.py` as the main file
5. Add secrets in the Streamlit Cloud dashboard (optional LLM keys only)
6. Click Deploy

> **Note:** The `expense_agent.db` file is created automatically on first run. It is excluded from version control by `.gitignore`.

---

## Supported Input Columns

| Canonical Name | Recognized Aliases |
|---|---|
| `transaction_id` | `id`, `txn_id`, `trans_id` |
| `transaction_date` | `date`, `txn_date`, `invoice_date`, `payment_date` |
| `vendor` | `vendor_name`, `supplier`, `merchant`, `payee` |
| `expense_category` | `category`, `expense_type`, `type`, `account` |
| `description` | `memo`, `details`, `notes`, `narrative` |
| `amount` | `total`, `total_amount`, `value`, `cost`, `debit` |
| `payment_reference` | `ref`, `reference`, `check_number`, `invoice_number` |
| `payment_method` | `method`, `pay_type`, `mode` |
| `department` | `dept`, `division`, `team`, `cost_center` |

---

## Disclaimer

> This tool provides decision-support signals only. All findings require manual verification against source documents. Estimated savings are projections based on documented assumptions and should not be recorded as realized savings. This tool does not provide financial, legal, or accounting advice. Consult a qualified financial professional before making significant financial decisions.

---

## Technology Stack

- **Frontend**: Streamlit ≥ 1.32
- **Data**: Pandas ≥ 2.1, NumPy ≥ 1.26
- **ML**: Scikit-learn ≥ 1.4 (Isolation Forest)
- **Visualization**: Plotly ≥ 5.18
- **Storage**: SQLite (via Python stdlib)
- **Reports**: OpenPyXL ≥ 3.1 (Excel)
- **Testing**: pytest ≥ 8.0, pytest-mock ≥ 3.12

---

## License

MIT License. See [LICENSE](LICENSE) for details.
