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


def calculate_campaign_metrics(campaign, profiles, rules):
    industry = campaign["industry"]
    budget   = campaign["budget"]
    profile  = profiles[industry]

    # ---------------------------------------------------------------
    # Step 1 — Apply per-campaign noise FIRST.
    #
    # Previous bug: impressions were derived from BASE ctr/cpc, but clicks
    # were computed with NOISY ctr/cpc applied to those same impressions.
    # This broke the fundamental identity:  impressions = clicks / CTR
    # because the two sides used different CTR values.
    #
    # Fix: draw noise once, then derive ALL downstream metrics (impressions,
    # clicks, conversions, cost) from the SAME noisy values — fully consistent.
    # ---------------------------------------------------------------
    ctr_noise   = random.normalvariate(0, rules["randomness"]["ctr_noise_std_dev"])
    target_ctr  = max(0.001, profile["ctr"] * (1 + ctr_noise))

    cpc_noise   = random.normalvariate(0, rules["randomness"]["cpc_noise_std_dev"])
    target_cpc  = max(0.10,  profile["cpc"] * (1 + cpc_noise))

    conv_noise       = random.normalvariate(0, rules["randomness"]["conversion_noise_std_dev"])
    target_conv_rate = max(0.001, profile["conversion_rate"] * (1 + conv_noise))

    # ---------------------------------------------------------------
    # Step 2 — Derive impressions from the SAME noisy values.
    #
    # Economic identity:
    #   clicks_possible = budget / CPC           (how many clicks this budget buys)
    #   impressions     = clicks_possible / CTR  (gross reach to produce those clicks)
    #
    # Seasonality is applied to impressions only (budget does not change,
    # but audience size and engagement rates shift with the season).
    # ---------------------------------------------------------------
    clicks_possible    = budget / target_cpc
    raw_impressions    = clicks_possible / target_ctr
    seasonality_mult   = get_seasonality_multiplier(
        campaign["start_date"], campaign["end_date"], profile
    )
    target_impressions = int(raw_impressions * seasonality_mult)

    # ---------------------------------------------------------------
    # Step 3 — Clicks and conversions.
    #
    # Model: each clicking user is either a non-converting click OR a conversion.
    # They are mutually exclusive events in the event log.
    #   total_clicks  = int(impressions × CTR)        — all click-equivalent actions
    #   conversions   = int(total_clicks × conv_rate) — subset that converted
    #   non_conv_clicks = total_clicks - conversions  — clicked but didn't convert
    # ---------------------------------------------------------------
    total_clicks      = int(target_impressions * target_ctr)
    conversions       = int(total_clicks * target_conv_rate)
    non_conv_clicks   = max(0, total_clicks - conversions)

    # ---------------------------------------------------------------
    # Step 4 — Cost (cap at budget).
    # Cost is driven by ALL click-equivalent events (converting + non-converting).
    # ---------------------------------------------------------------
    total_cost = round(total_clicks * target_cpc, 2)
    if total_cost > budget:
        total_cost        = budget
        total_clicks      = int(total_cost / target_cpc)
        conversions       = int(total_clicks * target_conv_rate)
        non_conv_clicks   = max(0, total_clicks - conversions)
        target_impressions = int(total_clicks / target_ctr) if target_ctr > 0 else 0

    # ---------------------------------------------------------------
    # Step 5 — avg_conversion_value returned for event-level revenue draws.
    # Revenue is NOT summed here. Each conversion event in the engagement
    # generator draws revenue INDEPENDENTLY (uniform ±30% around avg_value),
    # giving realistic per-event variance for the Revenue Prediction model.
    # ---------------------------------------------------------------
    avg_value = profile.get("avg_conversion_value", 1000)

    return {
        "impressions":          target_impressions,
        "total_clicks":         total_clicks,
        "non_conv_clicks":      non_conv_clicks,
        "conversions":          conversions,
        "cost":                 total_cost,
        "avg_conversion_value": avg_value,
    }
