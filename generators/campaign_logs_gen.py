import random
from datetime import datetime, timedelta

ADJECTIVES = ["Summer", "Winter", "Spring", "Autumn", "Holiday", "Festive", "NewYear", "Mega", "Flash", "Targeted",
              "YearEnd", "TaxSeason", "Monsoon", "Peak", "Premium"]
NOUNS = ["Sale", "Promo", "Launch", "Branding", "Drive", "Boost", "Push", "Awareness", "Conversion", "Engagement",
         "LeadGen", "Pipeline", "Acquisition", "Retention", "Reactivation"]

# Budget ranges in INR calibrated to Indian market cost tiers (per research benchmarks)
BUDGET_RANGES = {
    "bfsi":          (50000,  500000),   # High — high LTV of financial customers
    "insurance":     (80000,  800000),   # Highest — most expensive vertical
    "rcg":           (10000,  100000),   # Lowest — broad reach, impulse buys
    "travel":        (20000,  200000),   # Low-Mid — visually appealing, strong CTR
    "healthcare":    (30000,  300000),   # Mid-High — rising digital competition
    "manufacturing": (60000,  600000),   # High — niche B2B targeting, long cycles
}

# ---------------------------------------------------------------
# Channel weights per vertical.
# Reflects actual India media-mix reality:
#   - Manufacturing is LinkedIn-dominant (B2B)
#   - RCG is Meta/YouTube dominant (consumer impulse)
#   - BFSI/Insurance skew Google Search (high-intent, expensive)
#   - Travel is visual-first: Meta + YouTube
#   - Healthcare: organic/search-heavy but rising social
# ---------------------------------------------------------------
CHANNEL_WEIGHTS = {
    "bfsi":          {"Google Search": 0.40, "Meta": 0.28, "LinkedIn": 0.18, "YouTube": 0.10, "Google Display": 0.04},
    "insurance":     {"Google Search": 0.45, "Meta": 0.28, "LinkedIn": 0.15, "YouTube": 0.08, "Google Display": 0.04},
    "rcg":           {"Meta": 0.45, "YouTube": 0.25, "Instagram": 0.18, "Google Display": 0.08, "Google Search": 0.04},
    "travel":        {"Meta": 0.32, "Google Search": 0.28, "YouTube": 0.28, "Instagram": 0.12},
    "healthcare":    {"Google Search": 0.40, "Meta": 0.30, "YouTube": 0.18, "LinkedIn": 0.08, "Google Display": 0.04},
    "manufacturing": {"LinkedIn": 0.55, "Google Search": 0.28, "Industry Portals": 0.12, "YouTube": 0.05},
}

# ---------------------------------------------------------------
# Campaign objective weights per vertical.
# Manufacturing: Lead Gen dominant (B2B pipeline-first).
# Insurance: Lead Gen dominant (first-party data collection).
# RCG: Conversion + Engagement (impulse + brand loyalty).
# Travel: Brand Awareness + Conversion (intent phases).
# Healthcare: Awareness first (trust building), then Lead Gen.
# BFSI: Mix of Lead Gen and direct Conversion.
# ---------------------------------------------------------------
OBJECTIVE_WEIGHTS = {
    "bfsi":          {"Lead Generation": 0.40, "Conversion": 0.35, "Brand Awareness": 0.20, "Retention": 0.05},
    "insurance":     {"Lead Generation": 0.50, "Brand Awareness": 0.28, "Conversion": 0.17, "Retention": 0.05},
    "rcg":           {"Conversion": 0.38, "Brand Awareness": 0.28, "Engagement": 0.24, "Retention": 0.10},
    "travel":        {"Brand Awareness": 0.38, "Conversion": 0.35, "Engagement": 0.20, "Lead Generation": 0.07},
    "healthcare":    {"Brand Awareness": 0.38, "Lead Generation": 0.32, "Conversion": 0.22, "Retention": 0.08},
    "manufacturing": {"Lead Generation": 0.55, "Brand Awareness": 0.28, "Conversion": 0.12, "Retention": 0.05},
}

# ---------------------------------------------------------------
# Target segment weights per vertical.
# Manufacturing targets Enterprise/Mid-Market (B2B).
# RCG targets Consumer/Value (mass market).
# BFSI and Insurance span all tiers.
# ---------------------------------------------------------------
SEGMENT_WEIGHTS = {
    "bfsi":          {"Enterprise": 0.30, "Mid-Market": 0.38, "Consumer": 0.27, "Value": 0.05},
    "insurance":     {"Consumer": 0.40, "Mid-Market": 0.33, "Enterprise": 0.22, "Value": 0.05},
    "rcg":           {"Consumer": 0.52, "Value": 0.33, "Mid-Market": 0.12, "Enterprise": 0.03},
    "travel":        {"Consumer": 0.48, "Mid-Market": 0.30, "Value": 0.17, "Enterprise": 0.05},
    "healthcare":    {"Consumer": 0.45, "Mid-Market": 0.33, "Enterprise": 0.18, "Value": 0.04},
    "manufacturing": {"Enterprise": 0.45, "Mid-Market": 0.40, "Value": 0.10, "Consumer": 0.05},
}

# ---------------------------------------------------------------
# Creative type weights per vertical.
# Video dominates Travel and Insurance (emotional storytelling).
# Manufacturing uses Document (whitepapers, case studies) on LinkedIn.
# RCG leans Carousel (product grids) and Video (unboxing/influencer).
# ---------------------------------------------------------------
CREATIVE_WEIGHTS = {
    "bfsi":          {"Image": 0.38, "Video": 0.32, "Carousel": 0.22, "Text": 0.08},
    "insurance":     {"Video": 0.44, "Image": 0.32, "Carousel": 0.18, "Text": 0.06},
    "rcg":           {"Video": 0.35, "Carousel": 0.38, "Image": 0.22, "Text": 0.05},
    "travel":        {"Video": 0.50, "Image": 0.28, "Carousel": 0.18, "Text": 0.04},
    "healthcare":    {"Image": 0.42, "Video": 0.33, "Carousel": 0.18, "Text": 0.07},
    "manufacturing": {"Document": 0.35, "Image": 0.32, "Video": 0.22, "Text": 0.11},
}

# ---------------------------------------------------------------
# Audience size ranges per channel (number of unique users targeted).
# LinkedIn B2B audiences are niche and tight (5K–200K).
# Meta/Instagram can reach 100K–10M.
# Google Search is intent-based, typically 50K–5M.
# Industry Portals are small, specialist audiences.
# ---------------------------------------------------------------
AUDIENCE_SIZE_BY_CHANNEL = {
    "LinkedIn":         (5_000,    200_000),
    "Industry Portals": (3_000,     50_000),
    "Google Search":    (50_000,  5_000_000),
    "Google Display":   (100_000, 8_000_000),
    "Meta":             (100_000,10_000_000),
    "Instagram":        (80_000,  8_000_000),
    "YouTube":          (150_000,10_000_000),
}


def _weighted_choice(weight_dict):
    """Pick a key from a dict of {option: weight} using weighted random sampling."""
    keys = list(weight_dict.keys())
    weights = list(weight_dict.values())
    return random.choices(keys, weights=weights, k=1)[0]


def generate_campaign_logs(industry, volume, start_id=1,
                           date_range=None, target_channels=None,
                           campaign_objective=None, target_segment=None,
                           creative_type=None, target_audience_size=None,
                           budget_range=None):
    """
    Generate synthetic campaign log records for a specific industry.

    Parameters
    ----------
    industry : str
        The industry vertical key (e.g. "bfsi").
    volume : int
        Number of campaign records to generate.
    start_id : int
        The starting integer for campaign IDs (default 1).
    date_range : list[str] | None
        Optional ["YYYY-MM-DD", "YYYY-MM-DD"] window for campaign start dates.
    target_channels : list[str] | None
        Optional allowlist of channels (e.g. ["Meta", "LinkedIn"]).
    campaign_objective : str | None
        Optional fixed objective override (e.g. "Conversion", "Lead Generation").
    target_segment : str | None
        Optional fixed audience segment override (e.g. "Enterprise", "Consumer").
    creative_type : str | None
        Optional fixed creative type override (e.g. "Video", "Carousel").
    target_audience_size : int | None
        Optional fixed audience size override (e.g. 250000).
    budget_range : tuple[float, float] | None
        Optional (min_budget, max_budget) in INR override.
    """
    campaigns = []

    # --- Resolve date window ---
    if date_range and len(date_range) == 2:
        window_start = datetime.strptime(date_range[0], "%Y-%m-%d")
        window_end   = datetime.strptime(date_range[1], "%Y-%m-%d")
        if (window_end - window_start).days < 14:
            window_end = window_start + timedelta(days=60)
    else:
        window_start = datetime(2026, 1, 1)
        window_end   = datetime(2026, 10, 27)

    current_time = window_end
    total_window_days = max(1, (window_end - window_start).days)

    # --- Resolve channel weight subset ---
    full_channel_weights = CHANNEL_WEIGHTS.get(industry, {"Meta": 1.0})
    if target_channels:
        requested = {ch.strip() for ch in target_channels}
        filtered = {k: v for k, v in full_channel_weights.items() if k in requested}
        channel_weights_to_use = filtered if filtered else full_channel_weights
    else:
        channel_weights_to_use = full_channel_weights

    # Budget range resolution
    default_budget_lo, default_budget_hi = BUDGET_RANGES.get(industry, (10000, 100000))
    if budget_range and len(budget_range) == 2:
        lo, hi = budget_range
    else:
        lo, hi = default_budget_lo, default_budget_hi

    for i in range(volume):
        campaign_id = f"CAMP-{start_id + i:05d}"

        adj  = random.choice(ADJECTIVES)
        noun = random.choice(NOUNS)
        campaign_name = f"{industry.upper()}_{adj}_{noun}_{campaign_id}"

        budget = round(random.uniform(lo, hi), 2)

        start_offset  = random.randint(0, max(0, total_window_days - 14))
        duration_days = random.randint(14, 60)

        start_dt = window_start + timedelta(days=start_offset)
        end_dt   = start_dt + timedelta(days=duration_days)

        if end_dt < current_time:
            status = "Completed"
        elif start_dt <= current_time <= end_dt:
            status = "Active"
        else:
            status = "Paused"

        # Channel
        channel = _weighted_choice(channel_weights_to_use)

        # Objective (parameter override or vertical weight)
        if campaign_objective:
            objective = campaign_objective
        else:
            objective = _weighted_choice(OBJECTIVE_WEIGHTS.get(industry, {"Brand Awareness": 1.0}))

        # Segment (parameter override or vertical weight)
        if target_segment:
            segment = target_segment
        else:
            segment = _weighted_choice(SEGMENT_WEIGHTS.get(industry, {"Consumer": 1.0}))

        # Creative type (parameter override or vertical weight)
        if creative_type:
            creative = creative_type
        else:
            creative = _weighted_choice(CREATIVE_WEIGHTS.get(industry, {"Image": 1.0}))

        # Audience size (parameter override or channel universe)
        if target_audience_size:
            audience_size = int(target_audience_size)
        else:
            aud_lo, aud_hi = AUDIENCE_SIZE_BY_CHANNEL.get(channel, (50_000, 5_000_000))
            audience_size = random.randint(aud_lo, aud_hi)

        campaigns.append({
            "campaign_id":           campaign_id,
            "campaign_name":         campaign_name,
            "industry":              industry,
            "budget":                budget,
            "start_date":            start_dt.strftime("%Y-%m-%d"),
            "end_date":              end_dt.strftime("%Y-%m-%d"),
            "status":                status,
            "target_channel":        channel,
            "campaign_objective":    objective,
            "target_segment":        segment,
            "creative_type":         creative,
            "target_audience_size":  audience_size,
        })

    return campaigns