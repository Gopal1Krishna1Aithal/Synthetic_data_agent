"""
churn_labels.py — Ground-truth churn label engine for the Synthetic Data Agent.

PURPOSE (Phase 3)
=================
Agent 6 (Predictive Churn & Engagement Modeling) needs to train a classifier.
For that it needs labeled ground truth — a column that says "this customer DID
churn" or "this customer is at HIGH risk."

Without labels, Agent 6 would have to invent their own arbitrary threshold and
their model's ROC-AUC / Precision-Recall evaluation would be meaningless.

This module stamps four new fields onto every customer profile AFTER the LTV
roll-up has completed (so it has real spend and recency data, not zeros):

    days_since_last_purchase  int | None  — Recency signal (days ago from ref date)
    purchase_frequency        int         — count of conversion events attributed to customer
    churn_risk_tier           str         — "Low" | "Medium" | "High"
    is_churned                bool        — True when risk tier is "High"

CHURN WINDOW DESIGN
===================
Different industries have fundamentally different engagement cadences:

    RCG (Retail):       Expects weekly/monthly purchases. 60+ days = warning.
    Travel:             Trip-based. 1 trip/year is normal. 365+ days = churned.
    BFSI:               Annual products (loan EMI, SIP). 180 days = medium risk.
    Insurance:          Annual renewal cycle. 300 days without contact = high risk.
    Healthcare:         Episodic (appointment/prescription). 120 days = medium.
    Manufacturing:      B2B contract cycles 6–18 months. 180 days = medium risk.

NEVER PURCHASED CUSTOMERS
==========================
Customers with last_purchase_date = None have never converted.
They are always assigned "High" churn risk and is_churned = True regardless of
tenure — a first-purchase conversion is the most important event to predict.
"""

from datetime import date, datetime
from typing import Optional

# ---------------------------------------------------------------
# Industry-aware churn window config (days)
# (medium_threshold, high_threshold)
# medium: days_since_last_purchase > this → "Medium"
# high:   days_since_last_purchase > this → "High" (is_churned = True)
# ---------------------------------------------------------------
CHURN_WINDOWS = {
    #           medium_days  high_days
    "rcg":          (45,       90),     # Fast-moving consumer goods: frequent purchase expected
    "travel":       (180,      365),    # Trip-based: one trip per year is acceptable
    "bfsi":         (90,       180),    # Financial products: quarterly engagement expected
    "insurance":    (180,      300),    # Annual cycle; contact within 10 months = OK
    "healthcare":   (90,       180),    # Episodic; 6-month gap signals disengagement
    "manufacturing":(120,      240),    # B2B: longer cycles but contact expected bi-annually
}

# Default fallback if industry not in map
_DEFAULT_WINDOW = (90, 180)

# Reference "today" for recency calculation — matches customer_profiles_gen.py
_REFERENCE_DATE = date(2026, 8, 20)


def compute_churn_labels(
    customers: list,
    events: list,
    reference_date: Optional[date] = None,
) -> None:
    """
    Stamp ground-truth churn labels onto each customer record in-place.

    Must be called AFTER `_rollup_ltv()` so that `total_spend_to_date`
    and `last_purchase_date` reflect actual generated event data.

    Parameters
    ----------
    customers : list[dict]
        Customer profile records (mutated in-place).
    events : list[dict]
        All generated engagement events — used to count purchase_frequency
        per customer.
    reference_date : date, optional
        The "today" anchor for recency calculations.
        Defaults to 2026-08-20 (project reference date).

    Mutates each customer record by adding:
        days_since_last_purchase  : int | None
        purchase_frequency        : int
        churn_risk_tier           : "Low" | "Medium" | "High"
        is_churned                : bool
    """
    ref = reference_date or _REFERENCE_DATE

    # --- Build purchase frequency per customer from events ---
    freq_map: dict[str, int] = {}
    for evt in events:
        if evt["event_type"] == "conversion" and evt["customer_id"] is not None:
            cid = evt["customer_id"]
            freq_map[cid] = freq_map.get(cid, 0) + 1

    # --- Stamp labels ---
    for cust in customers:
        industry = cust.get("industry", "rcg")
        medium_days, high_days = CHURN_WINDOWS.get(industry, _DEFAULT_WINDOW)

        # Recency
        last_purchase = cust.get("last_purchase_date")
        if last_purchase is None:
            days_since = None
        else:
            if isinstance(last_purchase, str):
                last_purchase = datetime.strptime(last_purchase[:10], "%Y-%m-%d").date()
            days_since = max(0, (ref - last_purchase).days)

        # Purchase frequency: baseline past purchases + new conversions from this run
        base_freq = cust.get("purchase_frequency", 0)
        new_freq  = freq_map.get(cust["customer_id"], 0)
        freq      = base_freq + new_freq

        # Churn tier logic & top_drivers
        drivers = []

        if days_since is None:
            tier = "High"
            drivers.append("never_converted_post_signup")
            drivers.append("zero_monetary_contribution")
        elif days_since > high_days:
            tier = "High"
            drivers.append(f"inactivity_{days_since}_days_exceeds_threshold")
            if freq <= 1:
                drivers.append("single_purchase_lapse")
        elif days_since > medium_days:
            if freq >= 3:
                tier = "Low"
                drivers.append("retained_via_high_repeat_frequency")
            else:
                tier = "Medium"
                drivers.append(f"prolonged_recency_gap_{days_since}_days")
        else:
            tier = "Low"
            drivers.append("active_recent_engagement")
            if freq >= 3:
                drivers.append("loyal_repeat_buyer")

        # Spending signal override: high-spend customers with Medium recency are retained
        spend = cust.get("total_spend_to_date", 0.0)
        if tier == "Medium":
            spend_threshold = {
                "bfsi": 50000, "insurance": 30000, "rcg": 5000,
                "travel": 15000, "healthcare": 10000, "manufacturing": 200000,
            }.get(industry, 10000)
            if spend >= spend_threshold:
                tier = "Low"
                drivers.append("retained_via_high_monetary_spend")

        # Add segment context if value-sensitive
        if cust.get("segment") == "Value" and tier in ("Medium", "High"):
            drivers.append("price_sensitive_segment_risk")

        cust["days_since_last_purchase"] = days_since
        cust["purchase_frequency"]       = freq
        cust["churn_risk_tier"]          = tier
        cust["is_churned"]               = (tier == "High")
        cust["top_drivers"]              = drivers


def get_churn_summary(customers: list) -> dict:
    """
    Return a summary of churn label distribution across a customer list.
    Useful for the generation_report.

    Returns
    -------
    dict with keys:
        total, churned_count, churn_rate,
        tier_counts {"Low": int, "Medium": int, "High": int},
        never_purchased_count
    """
    total = len(customers)
    if total == 0:
        return {"total": 0, "churned_count": 0, "churn_rate": 0.0,
                "tier_counts": {}, "never_purchased_count": 0}

    tier_counts = {"Low": 0, "Medium": 0, "High": 0}
    churned = 0
    never_purchased = 0

    for c in customers:
        tier = c.get("churn_risk_tier", "High")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if c.get("is_churned", False):
            churned += 1
        if c.get("days_since_last_purchase") is None:
            never_purchased += 1

    return {
        "total":                total,
        "churned_count":        churned,
        "churn_rate":           round(churned / total, 4),
        "tier_counts":          tier_counts,
        "never_purchased_count": never_purchased,
    }

