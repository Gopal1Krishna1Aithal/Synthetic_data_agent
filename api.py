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
    parser = argparse.ArgumentParser(
        description="Synthetic Data Agent — generate industry-specific marketing datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Smallest valid run (all 6 verticals, minimal volume)
  python api.py

  # Specific verticals and volume
  python api.py --industries bfsi manufacturing --num-customers 500 --num-campaigns 50

  # CSV output with only churn-model fields
  python api.py --output-format csv --preset churn

  # Override CPC for a specific vertical
  python api.py --industries rcg --target-cpc 8.0

  # Validate schema without writing files
  python api.py --dry-run
"""
    )
    parser.add_argument("--industries", nargs="+",
                        default=["bfsi", "insurance", "rcg", "travel", "healthcare", "manufacturing"],
                        help="Verticals to generate. Default: all 6.")
    parser.add_argument("--num-customers", type=int, default=60,
                        help="Total customer profiles to generate (split evenly across industries). Default: 60.")
    parser.add_argument("--num-campaigns", type=int, default=12,
                        help="Total campaign logs to generate (split evenly across industries). Default: 12.")
    parser.add_argument("--output-format", choices=["json", "csv"], default="json",
                        help="Output file format. Default: json.")
    parser.add_argument("--output-dir", default="outputs",
                        help="Directory where generated files are saved. Default: outputs/.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate and validate data but DO NOT write any output files. Useful for testing.")
    parser.add_argument("--max-events-per-campaign", type=int, default=200,
                        help="Max engagement events written per campaign. Default: 200. "
                             "Higher = more detail, bigger files. Lower = faster, smaller files.")
    parser.add_argument("--conversions-only", action="store_true",
                        help="Filter out all impressions and clicks from the output (useful for presentations where you only want to see revenue rows).")

    # Output field presets — controls which columns appear in the output.
    # Use this to avoid bloated files when only specific downstream fields are needed.
    parser.add_argument("--preset", choices=["full", "churn", "channel", "campaign-performance"],
                        default="full",
                        help=(
                            "Field preset controlling which columns are written. "
                            "'full' = all fields (default). "
                            "'churn' = RFM fields for Churn Agent. "
                            "'channel' = acquisition fields for Channel Optimizer. "
                            "'campaign-performance' = campaign attribute + metric fields."
                        ))

    # Override-with-fallback seed parameters (run-scoped only; JSON never modified).
    parser.add_argument("--target-ctr", type=float, default=None,
                        help="Override CTR for all active industries (e.g. 0.025 for 2.5%%).")
    parser.add_argument("--target-cpc", type=float, default=None,
                        help="Override CPC in INR for all active industries (e.g. 40 for \u20b940/click).")
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
    # Dry-run uses a tiny event cap (20 per campaign) — just enough to validate schema.
    # Real runs use the --max-events-per-campaign value (default 200).
    event_cap = 20 if args.dry_run else args.max_events_per_campaign
    events = generate_engagement_events(campaigns, customers, profiles, rules,
                                        max_events_per_campaign=event_cap)
    
    if args.conversions_only:
        events = [e for e in events if e["event_type"] == "conversion"]
    
    # ---------------------------------------------------------------
    # Referential Integrity Roll-up: LTV Paradox Fix
    # ---------------------------------------------------------------
    # We generated initial customer profiles with 0 spend. Now we roll up
    # the actual revenue from their generated conversion events to perfectly
    # align LTV and recency with the event logs.
    customer_lookup = {c["customer_id"]: c for c in customers}
    
    for evt in events:
        if evt["event_type"] == "conversion" and evt["customer_id"] is not None:
            c = customer_lookup[evt["customer_id"]]
            c["total_spend_to_date"] = round(c["total_spend_to_date"] + evt["revenue"], 2)
            
            evt_date = evt["timestamp"][:10]  # Extract YYYY-MM-DD
            if c["last_purchase_date"] is None or evt_date > c["last_purchase_date"]:
                c["last_purchase_date"] = evt_date
    
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
    
    # ---------------------------------------------------------------
    # Field presets — filter output columns per downstream agent need.
    # ---------------------------------------------------------------
    PRESETS = {
        "full": {
            "customers": ["customer_id", "industry", "acquisition_channel", "name", "email",
                          "age", "gender", "segment", "signup_date", "total_spend_to_date",
                          "last_purchase_date"],
            "campaigns": ["campaign_id", "campaign_name", "industry", "budget", "start_date",
                          "end_date", "status", "target_channel", "campaign_objective",
                          "target_segment", "creative_type", "target_audience_size",
                          "reach", "impressions", "clicks", "conversions", "leads",
                          "spend", "cpm", "cpl"],
            "events":    ["event_id", "timestamp", "customer_id", "campaign_id", "event_type",
                          "industry", "attribution_weight", "cost", "revenue"],
        },
        "churn": {
            # RFM fields: Recency (last_purchase_date), Monetary (total_spend_to_date),
            # + segment and industry for stratified modelling
            "customers": ["customer_id", "industry", "segment", "acquisition_channel",
                          "signup_date", "total_spend_to_date", "last_purchase_date"],
            "campaigns": ["campaign_id", "industry", "target_segment", "campaign_objective"],
            "events":    ["event_id", "timestamp", "customer_id", "campaign_id",
                          "event_type", "revenue"],
        },
        "channel": {
            # Acquisition channel attribution for Channel Optimizer
            "customers": ["customer_id", "industry", "segment", "acquisition_channel",
                          "total_spend_to_date"],
            "campaigns": ["campaign_id", "industry", "target_channel", "budget",
                          "target_segment", "reach", "impressions", "conversions", "leads", "cpl"],
            "events":    ["event_id", "customer_id", "campaign_id", "event_type",
                          "industry", "attribution_weight", "cost"],
        },
        "campaign-performance": {
            # All campaign attributes + engagement metrics for Campaign Performance Agent
            "customers": ["customer_id", "industry", "segment"],
            "campaigns": ["campaign_id", "industry", "target_channel", "campaign_objective",
                          "target_segment", "creative_type", "target_audience_size",
                          "budget", "start_date", "end_date", "status", "reach", "impressions",
                          "clicks", "conversions", "leads", "spend", "cpm", "cpl"],
            "events":    ["event_id", "timestamp", "customer_id", "campaign_id",
                          "event_type", "industry", "attribution_weight", "cost", "revenue"],
        },
    }

    preset = PRESETS[args.preset]
    cust_fields = preset["customers"]
    camp_fields = preset["campaigns"]
    evt_fields  = preset["events"]

    # 5. Write outputs (skip if --dry-run)
    out_dir = os.path.join(base_dir, args.output_dir)

    if args.dry_run:
        print("[Dry Run] Validation complete. No files written (--dry-run flag set).")
        return

    os.makedirs(out_dir, exist_ok=True)

    def filter_fields(records, fields):
        """Return records with only the requested fields (silently skip missing ones)."""
        return [{f: r[f] for f in fields if f in r} for r in records]

    if args.output_format == "json":
        write_json(filter_fields(customers, cust_fields), os.path.join(out_dir, "customer_profiles.json"))
        write_json(filter_fields(campaigns, camp_fields), os.path.join(out_dir, "campaign_logs.json"))
        write_json(filter_fields(events,    evt_fields),  os.path.join(out_dir, "engagement_events.json"))
    else:
        write_csv(filter_fields(customers, cust_fields), os.path.join(out_dir, "customer_profiles.csv"),    cust_fields)
        write_csv(filter_fields(campaigns, camp_fields), os.path.join(out_dir, "campaign_logs.csv"),        camp_fields)
        write_csv(filter_fields(events,    evt_fields),  os.path.join(out_dir, "engagement_events.csv"),    evt_fields)

    # 6. Write Generation Report
    generation_report = {
        "parameters": vars(args),
        "volumes": {
            "customers_generated": len(customers),
            "campaigns_generated": len(campaigns),
            "events_generated": len(events)
        },
        "statistical_validation": stats_report
    }
    write_json(generation_report, os.path.join(out_dir, "generation_report.json"))

    print(f"\nSuccess! Generated logs saved to '{out_dir}' in {args.output_format.upper()} format.")
    print(f"Preset '{args.preset}' applied — {len(cust_fields)} customer fields, "
          f"{len(camp_fields)} campaign fields, {len(evt_fields)} event fields.")
    print(f"Generation report saved to '{os.path.join(out_dir, 'generation_report.json')}'.")

if __name__ == "__main__":
    main()
