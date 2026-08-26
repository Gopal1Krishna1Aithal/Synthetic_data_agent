import random
from datetime import datetime, timedelta, date

FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth",
               "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson",
              "Martinez", "Anderson", "Taylor", "Thomas", "Hernandez", "Moore", "Martin", "Jackson", "Thompson", "White"]
# RFC 2606 reserved domains — safe for synthetic/test data, never route to real mailboxes
DOMAINS = ["example.com", "example.org", "example.net", "mock-domain.test"]
GENDERS = ["Male", "Female", "Non-binary", "Other"]
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
    channel_weights = ACQUISITION_CHANNELS.get(industry, ACQUISITION_CHANNELS["rcg"])
    spend_multiplier = VERTICAL_SPEND_MULTIPLIER.get(industry, 1.0)
    customers = []
    start_date = datetime(2025, 1, 1)

    for i in range(volume):
        customer_id = f"CUST-{start_id + i:05d}"
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(10, 99)}@{random.choice(DOMAINS)}"
        age = random.randint(18, 75)
        gender = random.choice(GENDERS)
        segment = random.choice(SEGMENTS)

        # --- acquisition_channel: vertically-weighted ---
        acquisition_channel = _weighted_choice(channel_weights)

        # --- signup_date: sometime in the last 2 years ---
        days_ago = random.randint(0, 730)
        signup_date = (start_date - timedelta(days=days_ago)).date()

        # --- total_spend_to_date: segment range × vertical multiplier (INR) ---
        lo, hi = SPEND_BY_SEGMENT.get(segment, (500, 15000))
        total_spend = round(random.uniform(lo * spend_multiplier, hi * spend_multiplier), 2)

        # --- last_purchase_date: recency-gapped from today, nullable ---
        min_days, max_days, null_prob = RECENCY_CONFIG.get(segment, (30, 365, 0.10))
        if random.random() < null_prob:
            last_purchase_date = None
        else:
            # Recency gap from today, clamped so it can't precede signup_date
            days_since_purchase = random.randint(min_days, max_days)
            candidate = TODAY - timedelta(days=days_since_purchase)
            # Clamp: purchase must be on or after signup
            candidate = max(candidate, signup_date)
            last_purchase_date = candidate.isoformat()

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