import os
import argparse
import json
import csv
from generators.customer_profiles_gen import generate_customer_profiles
from generators.campaign_logs_gen import generate_campaign_logs
from generators.engagement_events_gen import generate_engagement_events
from validation import validate_schema, validate_statistics

def load_json_config(path):
    with open(path, 'r') as f:
        return json.load(f)

def write_csv(data, path, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)

def write_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Synthetic Data Agent CLI")
    parser.add_argument("--industries", nargs="+",
                        default=["bfsi", "insurance", "rcg", "travel", "healthcare", "manufacturing"],
                        help="List of industries to generate data for")
    parser.add_argument("--num-customers", type=int, default=100, help="Number of customer profiles to generate")
    parser.add_argument("--num-campaigns", type=int, default=10, help="Number of campaign logs to generate")
    parser.add_argument("--output-format", choices=["json", "csv"], default="json", help="Output file format")
    parser.add_argument("--output-dir", default="outputs", help="Directory where generated logs are saved")
    
    # Override-with-fallback seed parameters.
    # If passed, the value overrides the industry_profiles.json default for THIS run only.
    # Omitting a flag means the profile default is used — nothing in the JSON is ever touched.
    parser.add_argument("--target-ctr", type=float, default=None,
                        help="Override CTR for all active industries (e.g. 0.025 for 2.5%%).")
    parser.add_argument("--target-cpc", type=float, default=None,
                        help="Override CPC in INR for all active industries (e.g. 40 for ₹40/click).")
    parser.add_argument("--target-conversion-rate", type=float, default=None,
                        help="Override conversion rate for all active industries (e.g. 0.03 for 3%%).")
    
    args = parser.parse_args()
    
    # 1. Load configs
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profiles_path = os.path.join(base_dir, "config", "industry_profiles.json")
    rules_path = os.path.join(base_dir, "config", "relationship_rules.json")
    
    profiles = load_json_config(profiles_path)
    rules = load_json_config(rules_path)
    
    # Filter profiles to requested industries
    active_industries = [ind for ind in args.industries if ind in profiles]
    if not active_industries:
        print("Error: None of the specified industries exist in config.")
        return

    # Apply override-with-fallback: patch only the provided seed parameters in-memory.
    # The profile JSON on disk is NEVER modified — overrides are run-scoped only.
    overrides = {
        "ctr":             args.target_ctr,
        "cpc":             args.target_cpc,
        "conversion_rate": args.target_conversion_rate,
    }
    applied_overrides = {k: v for k, v in overrides.items() if v is not None}
    if applied_overrides:
        for ind in active_industries:
            profiles[ind].update(applied_overrides)
        override_summary = ", ".join(f"{k}={v}" for k, v in applied_overrides.items())
        print(f"[Override] Seed parameters applied for {active_industries}: {override_summary}")
        
    print(f"Generating data for industries: {active_industries}")
    
    # 2. Generate data
    customers = []
    campaigns = []
    
    cust_start_id = 1
    camp_start_id = 1
    
    # Calculate volume per industry (divide evenly, put remainder in the last one)
    num_ind = len(active_industries)
    cust_per_ind = args.num_customers // num_ind
    camp_per_ind = args.num_campaigns // num_ind
    cust_rem = args.num_customers % num_ind
    camp_rem = args.num_campaigns % num_ind

    for i, ind in enumerate(active_industries):
        c_vol = cust_per_ind + (cust_rem if i == num_ind - 1 else 0)
        p_vol = camp_per_ind + (camp_rem if i == num_ind - 1 else 0)
        
        # Warn if campaign count per vertical is too low for reliable conversion stats.
        # Low-conversion verticals (insurance, manufacturing) need ≥5 campaigns
        # for proportional sampling to capture rare conversion events accurately.
        if p_vol < 5:
            print(f"  [Warning] Only {p_vol} campaign(s) allocated to {ind.upper()}. "
                  f"Statistical accuracy for conversion_rate may be poor. "
                  f"Consider --num-campaigns {5 * num_ind} or more.")
        
        print(f"Generating data for {ind.upper()} ({c_vol} customers, {p_vol} campaigns)...")
        customers.extend(generate_customer_profiles(industry=ind, volume=c_vol, start_id=cust_start_id))
        campaigns.extend(generate_campaign_logs(industry=ind, volume=p_vol, start_id=camp_start_id))
        
        cust_start_id += c_vol
        camp_start_id += p_vol
        
    print("Generating engagement events...")
    events = generate_engagement_events(campaigns, customers, profiles, rules)
    
    # 3. Validate Schemas
    schema_dir = os.path.join(base_dir, "schemas")
    
    cust_ok, cust_msg = validate_schema(customers, os.path.join(schema_dir, "customer_profiles.schema.json"))
    camp_ok, camp_msg = validate_schema(campaigns, os.path.join(schema_dir, "campaign_logs.schema.json"))
    evt_ok, evt_msg = validate_schema(events, os.path.join(schema_dir, "engagement_events.schema.json"))
    
    print("\n--- Schema Validation Status ---")
    print(f"Customer Profiles Schema: {'PASSED' if cust_ok else 'FAILED'} - {cust_msg}")
    print(f"Campaign Logs Schema: {'PASSED' if camp_ok else 'FAILED'} - {camp_msg}")
    print(f"Engagement Events Schema: {'PASSED' if evt_ok else 'FAILED'} - {evt_msg}")
    print("--------------------------------\n")
    
    # 4. Statistical validation report
    stats_report = validate_statistics(campaigns, events, profiles)
    print("--- Statistical Validation Report ---")
    for r in stats_report:
        print(f"Industry: {r['industry'].upper()}")
        for metric, vals in r["metrics"].items():
            print(f"  {metric.upper()}: Actual={vals['actual']:.4f}, Target={vals['target']:.4f} (Dev={vals['deviation']*100:.2f}%)")
    print("-------------------------------------\n")
    
    # 5. Write outputs
    out_dir = os.path.join(base_dir, args.output_dir)
    os.makedirs(out_dir, exist_ok=True)
    
    if args.output_format == "json":
        write_json(customers, os.path.join(out_dir, "customer_profiles.json"))
        write_json(campaigns, os.path.join(out_dir, "campaign_logs.json"))
        write_json(events, os.path.join(out_dir, "engagement_events.json"))
    else:
        cust_fields = ["customer_id", "industry", "acquisition_channel", "name", "email", "age", "gender", "segment", "signup_date", "total_spend_to_date", "last_purchase_date"]
        camp_fields = ["campaign_id", "campaign_name", "industry", "budget", "start_date", "end_date",
                       "status", "target_channel", "campaign_objective", "target_segment",
                       "creative_type", "target_audience_size"]
        evt_fields = ["event_id", "timestamp", "customer_id", "campaign_id", "event_type", "industry", "attribution_weight", "cost", "revenue"]
        
        write_csv(customers, os.path.join(out_dir, "customer_profiles.csv"), cust_fields)
        write_csv(campaigns, os.path.join(out_dir, "campaign_logs.csv"), camp_fields)
        write_csv(events, os.path.join(out_dir, "engagement_events.csv"), evt_fields)
        
    print(f"Success! Generated logs saved to '{out_dir}' in {args.output_format.upper()} format.")

if __name__ == "__main__":
    main()
