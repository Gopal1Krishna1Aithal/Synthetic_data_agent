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

def generate_campaign_logs(industry, volume, start_id=1):
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
    """
    campaigns = []
    base_date = datetime(2026, 1, 1)

    for i in range(volume):
        campaign_id = f"CAMP-{start_id + i:05d}"
        
        adj = random.choice(ADJECTIVES)
        noun = random.choice(NOUNS)
        campaign_name = f"{industry.upper()}_{adj}_{noun}_{campaign_id}"

        # Budget range based on vertical cost tier
        lo, hi = BUDGET_RANGES.get(industry, (10000, 100000))
        budget = round(random.uniform(lo, hi), 2)

        # Campaign span
        start_offset = random.randint(0, 300)
        duration_days = random.randint(14, 60)

        start_dt = base_date + timedelta(days=start_offset)
        end_dt = start_dt + timedelta(days=duration_days)

        # Status based on current date (Aug 2026)
        current_time = datetime(2026, 8, 20)
        if end_dt < current_time:
            status = "Completed"
        elif start_dt <= current_time <= end_dt:
            status = "Active"
        else:
            status = "Paused"

        campaigns.append({
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "industry": industry,
            "budget": budget,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "status": status
        })

    return campaigns