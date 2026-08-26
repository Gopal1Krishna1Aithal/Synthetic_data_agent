import random
import math
from datetime import datetime

def get_seasonality_multiplier(start_date_str, end_date_str, profile):
    try:
        start_month = datetime.strptime(start_date_str, "%Y-%m-%d").month
        end_month = datetime.strptime(end_date_str, "%Y-%m-%d").month
    except ValueError:
        return 1.0
        
    months = list(range(start_month, end_month + 1)) if start_month <= end_month else list(range(start_month, 13)) + list(range(1, end_month + 1))
    multipliers = [profile["seasonality"].get(str(m), 1.0) for m in months]
    return sum(multipliers) / len(multipliers)

def calculate_campaign_metrics(campaign, profiles, rules):
    industry = campaign["industry"]
    budget = campaign["budget"]
    
    profile = profiles[industry]
    
    # 1. Impressions derived from budget and CPC (economically correct).
    #    clicks_possible = budget / cpc  (how many clicks the budget can buy)
    #    impressions = clicks_possible / ctr  (gross reach needed to produce those clicks)
    #
    #    The old power-law (100 * budget^0.95) was calibrated for low-CPC verticals only
    #    and produced wildly inflated impressions for high-CPC verticals like manufacturing
    #    (CPC ₹290), which caused the conversion rate to appear inflated in validation.
    
    # Pre-compute base CTR and CPC (noise added below, but use profile values here
    # for the impression estimate — noise is applied per-metric after)
    base_ctr = max(0.001, profile["ctr"])
    base_cpc = max(0.10,  profile["cpc"])
    
    clicks_possible = budget / base_cpc
    raw_impressions  = clicks_possible / base_ctr
    
    # Apply seasonality
    seasonality_mult = get_seasonality_multiplier(campaign["start_date"], campaign["end_date"], profile)
    target_impressions = int(raw_impressions * seasonality_mult)
    
    # Add noise to target CTR and CPC and Conversion Rate
    ctr_noise = random.normalvariate(0, rules["randomness"]["ctr_noise_std_dev"])
    target_ctr = max(0.001, profile["ctr"] * (1 + ctr_noise))
    
    cpc_noise = random.normalvariate(0, rules["randomness"]["cpc_noise_std_dev"])
    target_cpc = max(0.10, profile["cpc"] * (1 + cpc_noise))
    
    conv_noise = random.normalvariate(0, rules["randomness"]["conversion_noise_std_dev"])
    target_conv_rate = max(0.001, profile["conversion_rate"] * (1 + conv_noise))
    
    # 2. Clicks & Conversions
    clicks = int(target_impressions * target_ctr)
    conversions = int(clicks * target_conv_rate)
    
    # 3. Cost and Revenue
    total_cost = round(clicks * target_cpc, 2)
    # Cap total cost at budget
    if total_cost > budget:
        total_cost = budget
        clicks = int(total_cost / target_cpc)
        conversions = int(clicks * target_conv_rate)
        target_impressions = int(clicks / target_ctr) if target_ctr > 0 else 0
        
    # Read avg_conversion_value from the industry profile (INR)
    # Falls back to 1000 if the key is absent for forward compatibility
    avg_value = profile.get("avg_conversion_value", 1000)

    revenue = 0.0
    for _ in range(conversions):
        revenue += random.uniform(avg_value * 0.7, avg_value * 1.3)
    revenue = round(revenue, 2)
    
    return {
        "impressions": target_impressions,
        "clicks": clicks,
        "conversions": conversions,
        "cost": total_cost,
        "revenue": revenue
    }
