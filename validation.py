import json
import os

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

def validate_schema(data_list, schema_path):
    if not os.path.exists(schema_path):
        return False, f"Schema file not found: {schema_path}"
        
    with open(schema_path, 'r') as f:
        schema = json.load(f)
        
    if not HAS_JSONSCHEMA:
        # Fallback simple validation
        required_fields = schema.get("required", [])
        for idx, item in enumerate(data_list):
            for field in required_fields:
                if field not in item:
                    return False, f"Item at index {idx} missing required field '{field}'"
        return True, "Basic validation passed (jsonschema not installed)"

    # Compile the validator once to avoid massive overhead inside the loop
    try:
        validator = jsonschema.Draft7Validator(schema)
        for idx, item in enumerate(data_list):
            validator.validate(instance=item)
    except jsonschema.exceptions.ValidationError as e:
        return False, f"Item failed validation: {e.message}"
            
    return True, "All items match JSON schema successfully"

def validate_statistics(campaigns, events, profiles):
    # Group events by campaign
    campaign_stats = {}
    for camp in campaigns:
        campaign_stats[camp["campaign_id"]] = {
            "industry": camp["industry"],
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "cost": 0.0,
            "revenue": 0.0
        }
        
    for evt in events:
        cid = evt["campaign_id"]
        if cid in campaign_stats:
            etype = evt["event_type"]
            if etype == "impression":
                campaign_stats[cid]["impressions"] += 1
            elif etype == "click":
                campaign_stats[cid]["clicks"] += 1
                campaign_stats[cid]["cost"] += evt["cost"]
            elif etype == "conversion":
                campaign_stats[cid]["conversions"] += 1
                campaign_stats[cid]["revenue"] += evt["revenue"]
                
    # Check deviations per industry
    industry_sums = {}
    for cid, stats in campaign_stats.items():
        ind = stats["industry"]
        if ind not in industry_sums:
            industry_sums[ind] = {"impressions": 0, "clicks": 0, "conversions": 0, "cost": 0.0}
        # Add impressions (clicks and conversions are also impressions conceptually in downstream channels, 
        # but in our events list they are separate types)
        # Total impressions = impression events + click events + conversion events
        total_impressions = stats["impressions"] + stats["clicks"] + stats["conversions"]
        industry_sums[ind]["impressions"] += total_impressions
        industry_sums[ind]["clicks"] += stats["clicks"]
        industry_sums[ind]["conversions"] += stats["conversions"]
        industry_sums[ind]["cost"] += stats["cost"]
        
    report = []
    for ind, sums in industry_sums.items():
        profile = profiles.get(ind)
        if not profile:
            continue
            
        ctr = sums["clicks"] / sums["impressions"] if sums["impressions"] > 0 else 0
        cpc = sums["cost"] / sums["clicks"] if sums["clicks"] > 0 else 0
        conv_rate = sums["conversions"] / sums["clicks"] if sums["clicks"] > 0 else 0
        
        target_ctr = profile["ctr"]
        target_cpc = profile["cpc"]
        target_conv_rate = profile["conversion_rate"]
        
        ctr_dev = abs(ctr - target_ctr) / target_ctr if target_ctr > 0 else 0
        cpc_dev = abs(cpc - target_cpc) / target_cpc if target_cpc > 0 else 0
        conv_dev = abs(conv_rate - target_conv_rate) / target_conv_rate if target_conv_rate > 0 else 0
        
        report.append({
            "industry": ind,
            "metrics": {
                "ctr": {"actual": ctr, "target": target_ctr, "deviation": ctr_dev},
                "cpc": {"actual": cpc, "target": target_cpc, "deviation": cpc_dev},
                "conversion_rate": {"actual": conv_rate, "target": target_conv_rate, "deviation": conv_dev}
            }
        })
        
    return report
