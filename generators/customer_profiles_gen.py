import random
from datetime import datetime, timedelta, date

# Strictly anonymized data, no synthetic names allowed by policy
GENDERS  = ["Male", "Female", "Non-binary", "Other"]
SEGMENTS = ["Value", "Mid-Market", "Enterprise", "Consumer"]

# ---------------------------------------------------------------
# Acquisition channel mix by industry (must sum to 1.0 per row)
# Research rationale:
#   - Manufacturing/BFSI/Insurance: LinkedIn-heavy (B2B professional trust)
#   - RCG/Travel: Instagram+Facebook-heavy (visual, impulse-driven)
#   - Healthcare: Organic Search dominant (patients search symptoms first)
# ---------------------------------------------------------------
ACQUISITION_CHANNELS = {
    "bfsi":          {"Facebook": 0.25, "Instagram": 0.05, "LinkedIn": 0.35, "Organic_Search": 0.20, "Referral": 0.10, "Email": 0.05},
    "insurance":     {"Facebook": 0.28, "Instagram": 0.05, "LinkedIn": 0.30, "Organic_Search": 0.18, "Referral": 0.14, "Email": 0.05},
    "rcg":           {"Facebook": 0.30, "Instagram": 0.35, "LinkedIn": 0.03, "Organic_Search": 0.15, "Referral": 0.12, "Email": 0.05},
    "travel":        {"Facebook": 0.25, "Instagram": 0.35, "LinkedIn": 0.03, "Organic_Search": 0.22, "Referral": 0.10, "Email": 0.05},
    "healthcare":    {"Facebook": 0.20, "Instagram": 0.12, "LinkedIn": 0.10, "Organic_Search": 0.35, "Referral": 0.18, "Email": 0.05},
    "manufacturing": {"Facebook": 0.07, "Instagram": 0.03, "LinkedIn": 0.45, "Organic_Search": 0.20, "Referral": 0.20, "Email": 0.05},
}

# ---------------------------------------------------------------
# Total spend to date by segment (INR), per India e-commerce/B2B research:
#   Consumer: ₹650–₹850 quick-commerce AOV; ₹1K–₹3K D2C; up to ₹25K loyal shoppers
#   Mid-Market SME: ₹50K–₹5L annual (India MSME typical contract sizes)
#   Enterprise: ₹2L–₹5Cr+ (large B2B contracts, financial portfolio)
# ---------------------------------------------------------------
SPEND_BY_SEGMENT = {
    "Value":      (1000,    20000),     # Low-value, price-sensitive; 1–20K INR
    "Consumer":   (2000,    60000),     # Moderate retail/D2C buyer
    "Mid-Market": (75000,   750000),    # SME/MSME typical annual spend
    "Enterprise": (500000,  10000000),  # Large B2B/enterprise contracts
}

# Per-vertical multiplier applied ON TOP of segment ranges.
# Rationale: Enterprise Manufacturing deal > Enterprise RCG deal by 8–10x.
# Research: India B2B manufacturing avg deal ₹2L–₹5Cr vs RCG ₹10K–₹1L.
VERTICAL_SPEND_MULTIPLIER = {
    "bfsi":          2.0,   # High LTV: EMI commitments + investment portfolios
    "insurance":     1.8,   # Annual premium renewals compound over years
    "rcg":           0.5,   # Low-AOV consumer goods; RCG consumers spend less per account
    "travel":        1.0,   # Per-trip bookings, baseline
    "healthcare":    0.8,   # Episodic, out-of-pocket; lower annual commitment
    "manufacturing": 4.0,   # B2B contract values significantly exceed all B2C verticals
}

# ---------------------------------------------------------------
# Segment distribution per vertical (must mirror campaign_logs_gen.py SEGMENT_WEIGHTS
# so that campaign targeting actually reaches the right customer segment mix).
# Previous bug: random.choice(SEGMENTS) gave equal 25% per segment for ALL verticals,
# meaning a Manufacturing campaign targeting 45% Enterprise found only 25% Enterprise
# customers — creating a systematic targeting mismatch that would corrupt the
# downstream Campaign Performance model's audience-segment signal.
# ---------------------------------------------------------------
CUSTOMER_SEGMENT_WEIGHTS = {
    "bfsi":          {"Enterprise": 0.28, "Mid-Market": 0.37, "Consumer": 0.27, "Value": 0.08},
    "insurance":     {"Consumer": 0.40,   "Mid-Market": 0.33, "Enterprise": 0.20, "Value": 0.07},
    "rcg":           {"Consumer": 0.50,   "Value": 0.35,      "Mid-Market": 0.12, "Enterprise": 0.03},
    "travel":        {"Consumer": 0.47,   "Mid-Market": 0.28, "Value": 0.20,      "Enterprise": 0.05},
    "healthcare":    {"Consumer": 0.43,   "Mid-Market": 0.32, "Enterprise": 0.18, "Value": 0.07},
    "manufacturing": {"Enterprise": 0.43, "Mid-Market": 0.40, "Value": 0.12,      "Consumer": 0.05},
}

# ---------------------------------------------------------------
# Last purchase recency gaps (in days) from today (Aug 20 2026)
# Null probability = chance this customer has NEVER purchased.
# ---------------------------------------------------------------
TODAY = date(2026, 8, 20)

RECENCY_CONFIG = {
    #          (min_days_ago, max_days_ago, null_probability)
    "Enterprise": (10,  90,  0.00),   # Enterprise always active
    "Mid-Market": (15,  180, 0.05),
    "Consumer":   (20,  365, 0.15),
    "Value":      (90,  730, 0.20),   # High lapse risk
}


def _weighted_choice(weight_dict):
    """Pick a key from a dict of {key: weight} pairs."""
    keys = list(weight_dict.keys())
    weights = list(weight_dict.values())
    return random.choices(keys, weights=weights, k=1)[0]


def generate_customer_profiles(industry, volume, start_id=1):
    """
    Generate synthetic customer profiles for a specific industry.

    Parameters
    ----------
    industry : str
        The industry vertical key (e.g. "bfsi").
    volume : int
        Total number of customer records to generate.
    start_id : int
        The starting integer for customer IDs (default 1).

    Each customer includes:
    - acquisition_channel  : weighted by industry (for Channel Optimizer)
    - total_spend_to_date  : driven by segment + vertical multiplier (Churn "M" in RFM)
    - last_purchase_date   : driven by segment recency pattern (Churn "R" in RFM), nullable
    """
    channel_weights  = ACQUISITION_CHANNELS.get(industry, ACQUISITION_CHANNELS["rcg"])
    spend_multiplier = VERTICAL_SPEND_MULTIPLIER.get(industry, 1.0)
    customers = []

    for i in range(volume):
        customer_id = f"CUST-{start_id + i:05d}"
        
        # Strictly anonymized data, zero PII (not even synthetic names)
        name = f"User_{customer_id}"
        email = f"{customer_id.lower()}@anonymized.local"
        
        # --- Dirty data injection (2% missing values) ---
        age = random.randint(18, 75) if random.random() > 0.02 else None
        gender = random.choice(GENDERS) if random.random() > 0.02 else None

        # --- segment: industry-weighted distribution ---
        # Must mirror SEGMENT_WEIGHTS in campaign_logs_gen.py so campaign targeting
        # finds the correct customer mix (avoids systematic audience mismatch).
        seg_weights = CUSTOMER_SEGMENT_WEIGHTS.get(industry, {s: 0.25 for s in SEGMENTS})
        segment = _weighted_choice(seg_weights)

        # --- acquisition_channel: vertically-weighted ---
        acquisition_channel = _weighted_choice(channel_weights)

        # --- signup_date: last 2 years up to TODAY ---
        # Previous bug: was going backwards from datetime(2025,1,1), so no signups
        # after Jan 2025 — unrealistic for an active customer database.
        days_ago    = random.randint(0, 730)
        signup_date = (TODAY - timedelta(days=days_ago))

        # Initial LTV is 0. Revenue is aggregated dynamically from actual engagement events in api.py
        total_spend = 0.0
        last_purchase_date = None

        customers.append({
            "customer_id": customer_id,
            "industry": industry,
            "acquisition_channel": acquisition_channel,
            "name": name,
            "email": email,
            "age": age,
            "gender": gender,
            "segment": segment,
            "signup_date": signup_date.isoformat(),
            "total_spend_to_date": total_spend,
            "last_purchase_date": last_purchase_date,
        })

    return customers