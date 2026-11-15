"""
api.py — CLI entrypoint for the Synthetic Data Agent.

All generation logic lives in core.py. This file is a thin CLI wrapper
that parses arguments and delegates to generate_synthetic_data().

Usage:
    python api.py                                              # all 6 verticals, defaults
    python api.py --industry rcg --volume 500                 # 500 customers, RCG
    python api.py --industry bfsi --dataset-type campaign_logs --volume 200
    python api.py --industries bfsi rcg --volume 300 --output-format csv
    python api.py --industry travel --target-ctr 0.025 --dry-run
"""

import os
import json
import csv
import argparse

from core import generate_synthetic_data, VALID_INDUSTRIES

# ---------------------------------------------------------------
# Field presets — controls which columns appear in output files.
# Avoids bloated files when downstream agents only need a subset.
# ---------------------------------------------------------------
PRESETS = {
    "full": {
        "customers": [
            "customer_id", "industry", "acquisition_channel", "name", "email",
            "age", "gender", "segment", "signup_date", "total_spend_to_date",
            "last_purchase_date",
            # Phase 3: churn ground-truth labels
            "days_since_last_purchase", "purchase_frequency",
            "churn_risk_tier", "is_churned", "top_drivers",
        ],
        "campaigns": [
            "campaign_id", "campaign_name", "industry", "budget", "start_date",
            "end_date", "status", "target_channel", "campaign_objective",
            "target_segment", "creative_type", "target_audience_size",
            "reach", "impressions", "clicks", "conversions", "leads",
            "spend", "cpm", "cpl",
        ],
        "events": [
            "event_id", "timestamp", "customer_id", "campaign_id", "event_type",
            "industry", "attribution_weight", "cost", "revenue",
        ],
    },
    "churn": {
        # Full RFM + ground-truth labels for Agent 6 (Predictive Churn)
        "customers": [
            "customer_id", "industry", "segment", "acquisition_channel",
            "signup_date", "total_spend_to_date", "last_purchase_date",
            # Phase 3: ground-truth churn labels
            "days_since_last_purchase", "purchase_frequency",
            "churn_risk_tier", "is_churned", "top_drivers",
        ],
        "campaigns": ["campaign_id", "industry", "target_segment", "campaign_objective"],
        "events":    ["event_id", "timestamp", "customer_id", "campaign_id", "event_type", "revenue"],
    },
    "channel": {
        "customers": ["customer_id", "industry", "segment", "acquisition_channel", "total_spend_to_date"],
        "campaigns": [
            "campaign_id", "industry", "target_channel", "budget",
            "target_segment", "reach", "impressions", "conversions", "leads", "cpl",
        ],
        "events": ["event_id", "customer_id", "campaign_id", "event_type", "industry", "attribution_weight", "cost"],
    },
    "campaign-performance": {
        "customers": ["customer_id", "industry", "segment"],
        "campaigns": [
            "campaign_id", "industry", "target_channel", "campaign_objective",
            "target_segment", "creative_type", "target_audience_size",
            "budget", "start_date", "end_date", "status", "reach", "impressions",
            "clicks", "conversions", "leads", "spend", "cpm", "cpl",
        ],
        "events": [
            "event_id", "timestamp", "customer_id", "campaign_id",
            "event_type", "industry", "attribution_weight", "cost", "revenue",
        ],
    },
}


def _filter_fields(records, fields):
    """Return records with only the requested fields."""
    return [{f: r[f] for f in fields if f in r} for r in records]


def _write_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _write_csv(data, path, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def _run_industry(ind, args, out_dir, multiple_industries=False):
    """Generate and write data for a single industry."""

    seed_params = {}
    if args.target_ctr is not None:
        seed_params["target_ctr"] = args.target_ctr
    if args.target_cpc is not None:
        seed_params["target_cpc"] = args.target_cpc
    if args.target_conversion_rate is not None:
        seed_params["target_conversion_rate"] = args.target_conversion_rate

    result = generate_synthetic_data(
        industry=ind,
        dataset_type="all",
        volume=args.num_customers,
        seed_parameters=seed_params if seed_params else None,
        num_campaigns=args.num_campaigns,
        max_events_per_campaign=20 if args.dry_run else args.max_events_per_campaign,
        output_format="dict",
    )

    dataset      = result["synthetic_dataset"]
    gen_report   = result["generation_report"]
    val_score    = result["validation_score"]
    schema_val   = result["schema_validation"]

    customers = dataset.get("customers", [])
    campaigns = dataset.get("campaigns", [])
    events    = dataset.get("events", [])

    # --- Print validation ---
    print(f"\n  Schema Validation:")
    for ds_name, res in schema_val.items():
        status = "PASSED" if res["passed"] else ("SKIPPED" if res["passed"] is None else "FAILED")
        print(f"    {ds_name}: {status} — {res['message']}")

    print(f"\n  Statistical Validation (validation_score = {val_score}):")
    for r in gen_report["statistical_validation"]:
        print(f"    Industry: {r['industry'].upper()}")
        for metric, vals in r["metrics"].items():
            print(
                f"      {metric.upper()}: "
                f"Actual={vals['actual']:.4f}, "
                f"Target={vals['target']:.4f} "
                f"(Dev={vals['deviation'] * 100:.2f}%)"
            )

    if args.dry_run:
        print(f"\n  [Dry Run] Validation complete. No files written.")
        return gen_report

    # --- Write files ---
    preset       = PRESETS[args.preset]
    cust_fields  = preset["customers"]
    camp_fields  = preset["campaigns"]
    evt_fields   = preset["events"]

    ind_dir = os.path.join(out_dir, ind) if multiple_industries else out_dir
    os.makedirs(ind_dir, exist_ok=True)

    if args.output_format == "json":
        _write_json(_filter_fields(customers, cust_fields), os.path.join(ind_dir, "customer_profiles.json"))
        _write_json(_filter_fields(campaigns, camp_fields), os.path.join(ind_dir, "campaign_logs.json"))
        _write_json(_filter_fields(events, evt_fields),     os.path.join(ind_dir, "engagement_events.json"))
    else:
        _write_csv(_filter_fields(customers, cust_fields), os.path.join(ind_dir, "customer_profiles.csv"),    cust_fields)
        _write_csv(_filter_fields(campaigns, camp_fields), os.path.join(ind_dir, "campaign_logs.csv"),        camp_fields)
        _write_csv(_filter_fields(events, evt_fields),     os.path.join(ind_dir, "engagement_events.csv"),    evt_fields)

    _write_json(gen_report, os.path.join(ind_dir, "generation_report.json"))

    vols = gen_report["volumes"]
    print(
        f"\n  Written to '{ind_dir}': "
        f"{vols['customers_generated']} customers, "
        f"{vols['campaigns_generated']} campaigns, "
        f"{vols['events_generated']} events."
    )
    return gen_report


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic Data Agent — generate industry-specific marketing datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python api.py                                               # all 6 verticals, defaults
  python api.py --industries bfsi manufacturing --num-customers 500
  python api.py --industry rcg --num-customers 1000 --num-campaigns 100
  python api.py --output-format csv --preset churn
  python api.py --industries rcg --target-cpc 8.0 --dry-run
        """,
    )

    # Vertical selection (supports both singular and plural for convenience)
    ind_group = parser.add_mutually_exclusive_group()
    ind_group.add_argument(
        "--industry", dest="industry", default=None,
        help="Single industry vertical (e.g. rcg)."
    )
    ind_group.add_argument(
        "--industries", dest="industries", nargs="+", default=None,
        help="One or more verticals (e.g. bfsi rcg manufacturing). Default: all 6."
    )

    parser.add_argument("--num-customers",         type=int,   default=60,  help="Total customer profiles. Default: 60.")
    parser.add_argument("--num-campaigns",          type=int,   default=None, help="Total campaigns. Default: num-customers // 10.")
    parser.add_argument("--output-format",          choices=["json", "csv"], default="json")
    parser.add_argument("--output-dir",             default="outputs")
    parser.add_argument("--dry-run",                action="store_true", help="Validate without writing files.")
    parser.add_argument("--max-events-per-campaign",type=int,   default=200)
    parser.add_argument("--preset",                 choices=list(PRESETS.keys()), default="full")
    parser.add_argument("--target-ctr",             type=float, default=None)
    parser.add_argument("--target-cpc",             type=float, default=None)
    parser.add_argument("--target-conversion-rate", type=float, default=None)

    args = parser.parse_args()

    # Resolve industries list
    if args.industry:
        active_industries = [args.industry.lower()]
    elif args.industries:
        active_industries = [i.lower() for i in args.industries]
    else:
        active_industries = sorted(VALID_INDUSTRIES)

    invalid = [i for i in active_industries if i not in VALID_INDUSTRIES]
    if invalid:
        print(f"Error: Unknown industries: {invalid}. Valid: {sorted(VALID_INDUSTRIES)}")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir  = os.path.join(base_dir, args.output_dir)

    print(f"Generating data for industries: {active_industries}")
    print(f"Customers: {args.num_customers} | Preset: {args.preset} | Format: {args.output_format}")

    all_reports = []
    multiple_industries = len(active_industries) > 1
    for ind in active_industries:
        print(f"\n--- {ind.upper()} ---")
        report = _run_industry(ind, args, out_dir, multiple_industries=multiple_industries)
        all_reports.append(report)

    if not args.dry_run:
        print(f"\nDone! All outputs saved to '{out_dir}'.")


if __name__ == "__main__":
    main()
