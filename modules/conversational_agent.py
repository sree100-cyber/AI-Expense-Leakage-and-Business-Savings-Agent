"""
conversational_agent.py - Rule-based Q&A assistant + optional LLM integration.
"""
import os
import re
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple


# ────────────────────────────────────────────────────────────────────────────
# Rule-based answer engine
# ────────────────────────────────────────────────────────────────────────────

class RuleBasedAgent:
    """
    Answers expense questions using pre-computed analysis results.
    No LLM required — fully deterministic and transparent.
    """

    SUPPORTED_QUESTIONS = [
        "Which category has the highest spending?",
        "Which transactions may be duplicates?",
        "What are the top 3 cost-saving opportunities?",
        "How much is spent on subscriptions each month?",
        "What should the business review first?",
        "How many anomalies were detected?",
        "What is the total expenditure?",
        "Which vendor has the highest spend?",
        "What is the date range of this dataset?",
        "Show spending by department",
    ]

    def __init__(self, context: Dict[str, Any]):
        """
        context dict should contain:
          df            : clean transactions DataFrame
          exact_dups    : exact duplicate DataFrame
          possible_dups : possible duplicate DataFrame
          anomaly_df    : flagged anomalies DataFrame
          recommendations : list of recommendation dicts
          trends        : trend analysis result dict
          currency      : currency symbol string
        """
        self.ctx = context

    def _df(self) -> pd.DataFrame:
        return self.ctx.get("df", pd.DataFrame())

    def _recs(self) -> List[Dict]:
        return self.ctx.get("recommendations", [])

    def _currency(self) -> str:
        return self.ctx.get("currency", "USD")

    # ── Individual answer methods ────────────────────────────────────────────

    def top_spending_category(self) -> str:
        df = self._df()
        if df.empty or "expense_category" not in df.columns:
            return "No category data available."
        top = df.groupby("expense_category")["amount"].sum().idxmax()
        val = df.groupby("expense_category")["amount"].sum().max()
        return f"The highest-spending category is **{top}** with a total of {self._currency()} {val:,.2f}."

    def duplicate_summary(self) -> str:
        ex = self.ctx.get("exact_dups", pd.DataFrame())
        pos = self.ctx.get("possible_dups", pd.DataFrame())
        parts = []
        if not ex.empty:
            parts.append(
                f"- **{ex['duplicate_group_id'].nunique()} exact duplicate group(s)** "
                f"({len(ex)} transactions) sharing identical payment references."
            )
        if not pos.empty:
            parts.append(
                f"- **{pos['duplicate_group_id'].nunique()} possible duplicate group(s)** "
                f"({len(pos)} transactions) matching vendor + amount within a few days."
            )
        if not parts:
            return "No duplicate transactions were detected in the current dataset."
        return "Potential duplicate payment findings:\n" + "\n".join(parts)

    def top_3_recommendations(self) -> str:
        recs = [r for r in self._recs() if r.get("status") != "Rejected"]
        if not recs:
            return "No recommendations are available yet. Upload a dataset to generate insights."
        top3 = recs[:3]
        lines = [
            f"{i}. **{r['title']}** — estimated saving: "
            f"{self._currency()} {r.get('monthly_savings', 0):,.2f}/month "
            f"(Priority: {r.get('priority', 'N/A')})"
            for i, r in enumerate(top3, 1)
        ]
        return "Top 3 cost-saving opportunities:\n" + "\n".join(lines)

    def subscription_spend(self) -> str:
        recurring = self.ctx.get("trends", {}).get("recurring_expenses", pd.DataFrame())
        if recurring.empty:
            df = self._df()
            if df.empty:
                return "No subscription data available."
            sub_keywords = ["saas", "subscription", "software", "license", "cloud", "platform"]
            sub_mask = df["expense_category"].str.lower().str.contains(
                "|".join(sub_keywords), na=False
            )
            if not sub_mask.any():
                return "No clear subscription expenses identified in the current dataset."
            df_sub = df[sub_mask]
            df_sub = df_sub.copy()
            df_sub["year_month"] = df_sub["transaction_date"].dt.to_period("M")
            monthly_avg = df_sub.groupby("year_month")["amount"].sum().mean()
            return (
                f"Estimated average monthly subscription spend: "
                f"{self._currency()} {monthly_avg:,.2f} "
                f"(based on categories matching subscription keywords)."
            )

        consistent = recurring[recurring.get("pattern", pd.Series(dtype=str)) == "Consistent (subscription-like)"]
        if consistent.empty:
            total_monthly = recurring["avg_monthly_amount"].sum()
            return (
                f"No clearly consistent subscriptions detected. "
                f"Recurring vendor spend averages {self._currency()} {total_monthly:,.2f}/month across all recurring vendors."
            )

        total_monthly = consistent["avg_monthly_amount"].sum()
        vendors = ", ".join(consistent["vendor"].head(5).tolist())
        return (
            f"Estimated monthly subscription-like spend: {self._currency()} {total_monthly:,.2f} "
            f"across {len(consistent)} vendor(s) including {vendors}."
        )

    def what_to_review_first(self) -> str:
        recs = [r for r in self._recs() if r.get("priority") == "High"]
        if not recs:
            return (
                "No high-priority items detected. Review the Savings Recommendations page "
                "for medium-priority suggestions."
            )
        top = recs[0]
        return (
            f"The business should review **{top['title']}** first. "
            f"Evidence: {top['evidence']} "
            f"Suggested action: {top['action']}"
        )

    def anomaly_count(self) -> str:
        anomaly_df = self.ctx.get("anomaly_df", pd.DataFrame())
        if anomaly_df.empty:
            return "No unusual transactions were detected."
        return (
            f"**{len(anomaly_df)} unusual transaction(s)** were detected, "
            f"totaling {self._currency()} {anomaly_df['amount'].sum():,.2f}. "
            f"These were flagged by statistical analysis and/or machine learning."
        )

    def total_expenditure(self) -> str:
        df = self._df()
        if df.empty:
            return "No transaction data loaded."
        total = df["amount"].sum()
        n = len(df)
        return (
            f"Total expenditure in the current dataset: "
            f"**{self._currency()} {total:,.2f}** across {n:,} transactions."
        )

    def top_vendor(self) -> str:
        df = self._df()
        if df.empty or "vendor" not in df.columns:
            return "No vendor data available."
        top = df.groupby("vendor")["amount"].sum().idxmax()
        val = df.groupby("vendor")["amount"].sum().max()
        return f"The highest-spending vendor is **{top}** with {self._currency()} {val:,.2f}."

    def date_range(self) -> str:
        df = self._df()
        if df.empty or df["transaction_date"].isna().all():
            return "No date information available."
        min_d = df["transaction_date"].min().date()
        max_d = df["transaction_date"].max().date()
        return f"Dataset spans **{min_d}** to **{max_d}**."

    def dept_spending(self) -> str:
        df = self._df()
        if df.empty or "department" not in df.columns or df["department"].isna().all():
            return "No department information in the current dataset."
        dept = df.groupby("department")["amount"].sum().sort_values(ascending=False)
        lines = [f"- **{d}**: {self._currency()} {v:,.2f}" for d, v in dept.items()]
        return "Spending by department:\n" + "\n".join(lines)

    # ── Main dispatcher ──────────────────────────────────────────────────────

    _PATTERN_MAP = [
        (r"highest.{0,20}(spend|expenditure|cost|category)", "top_spending_category"),
        (r"top.{0,20}(category|spend|expenditure)", "top_spending_category"),
        (r"(duplicate|double.payment)", "duplicate_summary"),
        (r"top.{0,5}(3|three|saving|recommend|opportunit)", "top_3_recommendations"),
        (r"(recommend)", "top_3_recommendations"),
        (r"(subscription|saas|recurring)", "subscription_spend"),
        (r"(review first|priority|what should)", "what_to_review_first"),
        (r"(anomal|unusual|flagged)", "anomaly_count"),
        (r"(total.{0,10}(spend|expenditure|amount)|how much)", "total_expenditure"),
        (r"(top.{0,10}vendor|highest.{0,10}vendor)", "top_vendor"),
        (r"(date.range|time period|when)", "date_range"),
        (r"(department|dept|division)", "dept_spending"),
    ]

    def answer(self, question: str) -> str:
        if self._df().empty:
            return (
                "⚠️ No dataset is currently loaded. "
                "Please upload a file or load the sample data first."
            )
        q_lower = question.lower().strip()
        for pattern, method_name in self._PATTERN_MAP:
            if re.search(pattern, q_lower):
                return getattr(self, method_name)()
        return (
            "I couldn't match that question to a known pattern. Try asking about:\n"
            + "\n".join(f"- {q}" for q in self.SUPPORTED_QUESTIONS)
        )


# ────────────────────────────────────────────────────────────────────────────
# Optional LLM wrapper
# ────────────────────────────────────────────────────────────────────────────

def _build_llm_context(context: Dict) -> str:
    """Build a compact text summary of the analysis for LLM prompting."""
    df = context.get("df", pd.DataFrame())
    recs = context.get("recommendations", [])
    anomaly_df = context.get("anomaly_df", pd.DataFrame())
    currency = context.get("currency", "USD")

    lines = ["=== EXPENSE ANALYSIS SUMMARY ==="]
    if not df.empty:
        lines.append(f"Total transactions: {len(df)}")
        lines.append(f"Total spend: {currency} {df['amount'].sum():,.2f}")
        lines.append(f"Date range: {df['transaction_date'].min().date()} to {df['transaction_date'].max().date()}")
        top_cat = df.groupby("expense_category")["amount"].sum().nlargest(3)
        lines.append("Top categories: " + ", ".join([f"{k}: {currency} {v:,.0f}" for k, v in top_cat.items()]))

    lines.append(f"Anomalies detected: {len(anomaly_df)}")
    lines.append(f"Recommendations: {len(recs)}")
    for r in recs[:5]:
        lines.append(f"  [{r.get('priority','?')}] {r.get('title','?')} — est. savings {currency} {r.get('monthly_savings',0):,.0f}/mo")

    return "\n".join(lines)


def get_llm_answer(question: str, context: Dict) -> Optional[str]:
    """
    Try to get an answer from an LLM if API keys are configured.
    Returns None if no LLM is available (caller falls back to rule-based).
    Never exposes API keys to the user.
    """
    provider = os.getenv("LLM_PROVIDER", "").lower()
    ctx_text = _build_llm_context(context)
    system_prompt = (
        "You are an AI expense analysis assistant. "
        "Answer user questions about their business expense data based on the analysis summary below. "
        "Be concise and factual. Clearly distinguish estimates from confirmed findings. "
        "Never fabricate specific numbers that aren't in the summary.\n\n"
        + ctx_text
    )

    try:
        if provider == "openai":
            import openai
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                max_tokens=400,
                temperature=0.2,
            )
            return resp.choices[0].message.content

        elif provider == "google":
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(system_prompt + "\n\nUser: " + question)
            return resp.text

        elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            resp = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=400,
                system=system_prompt,
                messages=[{"role": "user", "content": question}],
            )
            return resp.content[0].text

    except Exception:
        return None

    return None


def get_answer(question: str, context: Dict):
    """
    Main entry point: try LLM first, fall back to rule-based.
    Returns (answer_text, source) where source is 'LLM' or 'Rule-based'.
    """
    llm_answer = get_llm_answer(question, context)
    if llm_answer:
        return llm_answer, "LLM"

    agent = RuleBasedAgent(context)
    return agent.answer(question), "Rule-based"
