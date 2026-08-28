"""
relationships.py — Campaign metric calculator with attribute-driven signal.

MATHEMATICAL DESIGN
===================
Industry profile CPC/CTR/CR = the EXPECTED BLENDED AVERAGE across that vertical's
typical campaign mix. Attribute multipliers represent how each specific attribute
combination deviates from that blended average.

NORMALIZATION GUARANTEE
=======================
For each industry, the weighted average of channel/creative/objective/segment
multipliers = 1.0. This ensures the industry profile benchmarks remain the
statistical mean — individual campaigns deviate up/down based on their attributes,
but the aggregate converges to the profile value at large n.

Without normalization, channel-dominated verticals diverge:
  Manufacturing (55% LinkedIn, CPC×1.70): weighted avg = 1.54× → 54% above profile
  RCG (45% Meta, CPC×0.40): weighted avg = 0.48× → 52% below profile

With normalization, both converge to 1.0 by construction.
"""

import random
from datetime import datetime


def get_seasonality_multiplier(start_date_str, end_date_str, profile):
    try:
        start_month = datetime.strptime(start_date_str, "%Y-%m-%d").month
        end_month   = datetime.strptime(end_date_str,   "%Y-%m-%d").month
    except ValueError:
        return 1.0

    months = (
        list(range(start_month, end_month + 1))
        if start_month <= end_month
        else list(range(start_month, 13)) + list(range(1, end_month + 1))
    )
    multipliers = [profile["seasonality"].get(str(m), 1.0) for m in months]
    return sum(multipliers) / len(multipliers)


# ---------------------------------------------------------------
# RAW ATTRIBUTE MULTIPLIERS
# (ctr_mult, cpc_mult, cr_mult)
#
# These represent the RELATIVE ordering of channels/creatives/
# objectives/segments — not their absolute deviation from the profile.
# The normalization step below ensures weighted averages = 1.0.
#
# Sources:
#   Channel CPC ratios: LinkedIn/Meta ~4-5× global; Search/Meta ~3×
#   Channel CTR ratios: Search ~3-5× display (Google benchmark data 2024)
#   Creative CTR lift: Video +20-50% vs Image (Meta internal 2023)
#   Objective CR lift: Conversion-optimised +60-80% vs blended (Meta 2023)
#   Segment bid adjustment: Enterprise +40-50% CPC (LinkedIn audience data)
# ---------------------------------------------------------------

CHANNEL_MULTIPLIERS = {
    "Google Search":    (2.00, 1.20, 1.40),
    "LinkedIn":         (0.25, 1.70, 1.15),
    "Meta":             (1.15, 0.40, 1.00),
    "Instagram":        (1.25, 0.38, 0.88),
    "Google Display":   (0.40, 0.22, 0.72),
    "YouTube":          (0.35, 0.68, 0.68),
    "Industry Portals": (0.30, 1.90, 1.25),
}

CREATIVE_MULTIPLIERS = {
    "Video":            (1.20, 1.05, 0.90),
    "Carousel":         (1.12, 1.00, 1.08),
    "Image":            (1.00, 1.00, 1.00),
    "Document":         (0.70, 0.95, 1.12),
    "Text":             (0.72, 0.85, 1.04),
}

OBJECTIVE_MULTIPLIERS = {
    "Conversion":       (1.00, 1.20, 1.70),
    "Lead Generation":  (1.05, 1.12, 1.35),
    "Brand Awareness":  (0.90, 0.78, 0.35),
    "Engagement":       (1.18, 0.92, 0.55),
    "Retention":        (1.10, 1.08, 1.60),
}

SEGMENT_MULTIPLIERS = {
    "Enterprise":       (0.90, 1.45, 1.15),
    "Mid-Market":       (0.95, 1.20, 1.08),
    "Consumer":         (1.00, 1.00, 1.00),
    "Value":            (1.05, 0.82, 0.72),
}

# ---------------------------------------------------------------
# INDUSTRY ATTRIBUTE DISTRIBUTIONS
# Mirrors campaign_logs_gen.py exactly. Duplicated here to keep
# relationships.py self-contained (avoids cross-module imports).
# ---------------------------------------------------------------
_CHANNEL_WEIGHTS = {
    "bfsi":          {"Google Search": 0.40, "Meta": 0.28, "LinkedIn": 0.18, "YouTube": 0.10, "Google Display": 0.04},
    "insurance":     {"Google Search": 0.45, "Meta": 0.28, "LinkedIn": 0.15, "YouTube": 0.08, "Google Display": 0.04},
    "rcg":           {"Meta": 0.45, "YouTube": 0.25, "Instagram": 0.18, "Google Display": 0.08, "Google Search": 0.04},
    "travel":        {"Meta": 0.32, "Google Search": 0.28, "YouTube": 0.28, "Instagram": 0.12},
    "healthcare":    {"Google Search": 0.40, "Meta": 0.30, "YouTube": 0.18, "LinkedIn": 0.08, "Google Display": 0.04},
    "manufacturing": {"LinkedIn": 0.55, "Google Search": 0.28, "Industry Portals": 0.12, "YouTube": 0.05},
}

_CREATIVE_WEIGHTS = {
    "bfsi":          {"Image": 0.38, "Video": 0.32, "Carousel": 0.22, "Text": 0.08},
    "insurance":     {"Video": 0.44, "Image": 0.32, "Carousel": 0.18, "Text": 0.06},
    "rcg":           {"Video": 0.35, "Carousel": 0.38, "Image": 0.22, "Text": 0.05},
    "travel":        {"Video": 0.50, "Image": 0.28, "Carousel": 0.18, "Text": 0.04},
    "healthcare":    {"Image": 0.42, "Video": 0.33, "Carousel": 0.18, "Text": 0.07},
    "manufacturing": {"Document": 0.35, "Image": 0.32, "Video": 0.22, "Text": 0.11},
}

_OBJECTIVE_WEIGHTS = {
    "bfsi":          {"Lead Generation": 0.40, "Conversion": 0.35, "Brand Awareness": 0.20, "Retention": 0.05},
    "insurance":     {"Lead Generation": 0.50, "Brand Awareness": 0.28, "Conversion": 0.17, "Retention": 0.05},
    "rcg":           {"Conversion": 0.38, "Brand Awareness": 0.28, "Engagement": 0.24, "Retention": 0.10},
    "travel":        {"Brand Awareness": 0.38, "Conversion": 0.35, "Engagement": 0.20, "Lead Generation": 0.07},
    "healthcare":    {"Brand Awareness": 0.38, "Lead Generation": 0.32, "Conversion": 0.22, "Retention": 0.08},
    "manufacturing": {"Lead Generation": 0.55, "Brand Awareness": 0.28, "Conversion": 0.12, "Retention": 0.05},
}

_SEGMENT_WEIGHTS = {
    "bfsi":          {"Enterprise": 0.28, "Mid-Market": 0.37, "Consumer": 0.27, "Value": 0.08},
    "insurance":     {"Consumer": 0.40, "Mid-Market": 0.33, "Enterprise": 0.20, "Value": 0.07},
    "rcg":           {"Consumer": 0.50, "Value": 0.35, "Mid-Market": 0.12, "Enterprise": 0.03},
    "travel":        {"Consumer": 0.47, "Mid-Market": 0.28, "Value": 0.20, "Enterprise": 0.05},
    "healthcare":    {"Consumer": 0.43, "Mid-Market": 0.32, "Enterprise": 0.18, "Value": 0.07},
    "manufacturing": {"Enterprise": 0.43, "Mid-Market": 0.40, "Value": 0.12, "Consumer": 0.05},
}


def _compute_norm_factors(weight_dict, mult_dict, default=(1.0, 1.0, 1.0)):
    """
    For each industry, compute the weighted average of (ctr_mult, cpc_mult, cr_mult)
    across that industry's attribute distribution.
    Returns {industry: (avg_ctr_mult, avg_cpc_mult, avg_cr_mult)}.
    Used to normalize multipliers so weighted average = 1.0.
    """
    norms = {}
    for industry, weights in weight_dict.items():
        total_weight = sum(weights.values())
        avg_ctr = sum(weights[a] * mult_dict.get(a, default)[0] for a in weights) / total_weight
        avg_cpc = sum(weights[a] * mult_dict.get(a, default)[1] for a in weights) / total_weight
        avg_cr  = sum(weights[a] * mult_dict.get(a, default)[2] for a in weights) / total_weight
        norms[industry] = (avg_ctr, avg_cpc, avg_cr)
    return norms


# Pre-compute normalization factors once at module load (O(1) per lookup at runtime)
_NORM_CHANNEL   = _compute_norm_factors(_CHANNEL_WEIGHTS,   CHANNEL_MULTIPLIERS)
_NORM_CREATIVE  = _compute_norm_factors(_CREATIVE_WEIGHTS,  CREATIVE_MULTIPLIERS)
_NORM_OBJECTIVE = _compute_norm_factors(_OBJECTIVE_WEIGHTS, OBJECTIVE_MULTIPLIERS)
_NORM_SEGMENT   = _compute_norm_factors(_SEGMENT_WEIGHTS,   SEGMENT_MULTIPLIERS)


def _apply_multipliers(campaign, base_ctr, base_cpc, base_cr):
    """
    Apply attribute-driven multipliers, normalized so the industry-weighted
    average of all multipliers = 1.0 for each metric.

    Result: individual campaigns deviate from the profile benchmark based on
    their specific attribute combination, but the AGGREGATE across all campaigns
    in a vertical converges to the profile value (unbiased at large n).
    """
    industry  = campaign.get("industry",          "bfsi")
    channel   = campaign.get("target_channel",    "Meta")
    creative  = campaign.get("creative_type",      "Image")
    objective = campaign.get("campaign_objective", "Brand Awareness")
    segment   = campaign.get("target_segment",     "Consumer")

    # Raw multipliers
    ch_ctr,  ch_cpc,  ch_cr  = CHANNEL_MULTIPLIERS.get(  channel,   (1.0, 1.0, 1.0))
    cr_ctr,  cr_cpc,  cr_cr  = CREATIVE_MULTIPLIERS.get( creative,  (1.0, 1.0, 1.0))
    ob_ctr,  ob_cpc,  ob_cr  = OBJECTIVE_MULTIPLIERS.get(objective, (1.0, 1.0, 1.0))
    sg_ctr,  sg_cpc,  sg_cr  = SEGMENT_MULTIPLIERS.get(  segment,   (1.0, 1.0, 1.0))

    # Industry-specific normalization factors (all default to 1.0 for unknown industries)
    n_ch_ctr,  n_ch_cpc,  n_ch_cr  = _NORM_CHANNEL.get(  industry, (1.0, 1.0, 1.0))
    n_cr_ctr,  n_cr_cpc,  n_cr_cr  = _NORM_CREATIVE.get( industry, (1.0, 1.0, 1.0))
    n_ob_ctr,  n_ob_cpc,  n_ob_cr  = _NORM_OBJECTIVE.get(industry, (1.0, 1.0, 1.0))
    n_sg_ctr,  n_sg_cpc,  n_sg_cr  = _NORM_SEGMENT.get(  industry, (1.0, 1.0, 1.0))

    # Normalized multipliers: each group's contribution averages to 1.0 per industry
    final_ctr = base_ctr * (ch_ctr/n_ch_ctr) * (cr_ctr/n_cr_ctr) * (ob_ctr/n_ob_ctr) * (sg_ctr/n_sg_ctr)
    final_cpc = base_cpc * (ch_cpc/n_ch_cpc) * (cr_cpc/n_cr_cpc) * (ob_cpc/n_ob_cpc) * (sg_cpc/n_sg_cpc)
    final_cr  = base_cr  * (ch_cr /n_ch_cr)  * (cr_cr /n_cr_cr)  * (ob_cr /n_ob_cr)  * (sg_cr /n_sg_cr)

    return final_ctr, final_cpc, final_cr


def calculate_campaign_metrics(campaign, profiles, rules):
    industry = campaign["industry"]
    budget   = campaign["budget"]
    profile  = profiles[industry]

    # Step 1 — Per-campaign noise
    ctr_noise  = random.normalvariate(0, rules["randomness"]["ctr_noise_std_dev"])
    base_ctr   = max(0.001, profile["ctr"] * (1 + ctr_noise))

    cpc_noise  = random.normalvariate(0, rules["randomness"]["cpc_noise_std_dev"])
    base_cpc   = max(0.10,  profile["cpc"] * (1 + cpc_noise))

    conv_noise = random.normalvariate(0, rules["randomness"]["conversion_noise_std_dev"])
    base_cr    = max(0.001, profile["conversion_rate"] * (1 + conv_noise))

    # Step 2 — Normalized attribute multipliers
    target_ctr, target_cpc, target_cr = _apply_multipliers(
        campaign, base_ctr, base_cpc, base_cr
    )

    # Clamp to physically sensible bounds
    target_ctr = min(max(target_ctr, 0.001), 0.30)
    target_cpc = max(target_cpc, 0.10)
    target_cr  = min(max(target_cr,  0.001), 0.80)

    # Step 3 — Impressions (economic identity: budget / CPC / CTR)
    clicks_possible    = budget / target_cpc
    raw_impressions    = clicks_possible / target_ctr
    seasonality_mult   = get_seasonality_multiplier(
        campaign["start_date"], campaign["end_date"], profile
    )
    target_impressions = int(raw_impressions * seasonality_mult)

    # Step 4 — Clicks split into non-converting and converting (mutually exclusive)
    total_clicks    = int(target_impressions * target_ctr)
    conversions     = int(total_clicks * target_cr)
    non_conv_clicks = max(0, total_clicks - conversions)

    # Step 5 — Cost capped at budget
    total_cost = round(total_clicks * target_cpc, 2)
    if total_cost > budget:
        total_cost      = budget
        total_clicks    = int(total_cost / target_cpc)
        conversions     = int(total_clicks * target_cr)
        non_conv_clicks = max(0, total_clicks - conversions)
        target_impressions = int(total_clicks / target_ctr) if target_ctr > 0 else 0

    avg_value = profile.get("avg_conversion_value", 1000)

    return {
        "impressions":          target_impressions,
        "total_clicks":         total_clicks,
        "non_conv_clicks":      non_conv_clicks,
        "conversions":          conversions,
        "cost":                 total_cost,
        "avg_conversion_value": avg_value,
    }
