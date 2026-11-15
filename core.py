"""
core.py — Programmatic API for the Synthetic Data Agent.

This module exposes `generate_synthetic_data()`, the canonical importable
function that any downstream agent (or FastAPI server) calls directly.

Downstream usage example:
    from core import generate_synthetic_data

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="campaign_logs",
        volume=500,
        seed_parameters={"target_ctr": 0.03, "target_cpc": 12.0}
    )
    print(result["validation_score"])   # e.g. 0.9712
    df = pd.DataFrame(result["synthetic_dataset"])
"""

import os
import json
import copy
from typing import Literal, Optional

from generators.customer_profiles_gen import generate_customer_profiles
from generators.campaign_logs_gen import generate_campaign_logs
from generators.engagement_events_gen import generate_engagement_events
from validation import validate_schema, validate_statistics, compute_comprehensive_validation
from churn_labels import compute_churn_labels, get_churn_summary

# ---------------------------------------------------------------
# Config paths (resolved relative to this file so the module is
# importable from any working directory)
# ---------------------------------------------------------------
_BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
_PROFILES_PATH = os.path.join(_BASE_DIR, "config", "industry_profiles.json")
_RULES_PATH    = os.path.join(_BASE_DIR, "config", "relationship_rules.json")
_SCHEMA_DIR    = os.path.join(_BASE_DIR, "schemas")

# Supported dataset types
DATASET_TYPES = Literal["customer_profiles", "campaign_logs", "engagement_events", "all"]

# Valid industry keys
VALID_INDUSTRIES = {"bfsi", "insurance", "rcg", "travel", "healthcare", "manufacturing"}


def _load_configs():
    """Load and return (profiles, rules) config dicts."""
    with open(_PROFILES_PATH, "r") as f:
        profiles = json.load(f)
    with open(_RULES_PATH, "r") as f:
        rules = json.load(f)
    return profiles, rules


def _apply_seed_parameters(profiles: dict, industry: str, seed_parameters: dict) -> dict:
    """
    Apply optional seed_parameters overrides in-memory for one industry.
    The on-disk JSON is NEVER modified. Supported keys:
        target_ctr             (float) — override CTR for this run
        target_cpc             (float) — override CPC in INR for this run
        target_conversion_rate (float) — override conversion rate for this run
        avg_ctr_range          (list)  — [lo, hi] range; midpoint used as target_ctr
        date_range             (list)  — ["YYYY-MM-DD", "YYYY-MM-DD"] campaign window
        target_channels        (list)  — allowlist of channels, e.g. ["Meta", "LinkedIn"]
    Note: date_range and target_channels are extracted and returned separately
    since they control generation, not benchmark profiles.
    """
    profiles = copy.deepcopy(profiles)  # never mutate the caller's dict

    if not seed_parameters:
        return profiles

    mapping = {
        "target_ctr":             "ctr",
        "target_cpc":             "cpc",
        "target_conversion_rate": "conversion_rate",
    }

    for param_key, profile_key in mapping.items():
        if param_key in seed_parameters:
            profiles[industry][profile_key] = float(seed_parameters[param_key])

    # avg_ctr_range: use midpoint as the target CTR
    if "avg_ctr_range" in seed_parameters:
        lo, hi = seed_parameters["avg_ctr_range"]
        profiles[industry]["ctr"] = (lo + hi) / 2.0

    return profiles


def _extract_generation_params(seed_parameters: dict) -> dict:
    """
    Extract Phase 2 generation-control params from seed_parameters.
    These don't go into profiles — they control the generators directly.

    Returns
    -------
    dict with keys:
        date_range           : list[str] | None
        target_channels      : list[str] | None
        campaign_objective   : str | None
        target_segment       : str | None
        creative_type        : str | None
        target_audience_size : int | None
        budget_range         : tuple | None
        baseline_history     : bool
    """
    if not seed_parameters:
        return {
            "date_range":           None,
            "target_channels":      None,
            "campaign_objective":   None,
            "target_segment":       None,
            "creative_type":        None,
            "target_audience_size": None,
            "budget_range":         None,
            "baseline_history":     True,
        }
    return {
        "date_range":           seed_parameters.get("date_range"),
        "target_channels":      seed_parameters.get("target_channels"),
        "campaign_objective":   seed_parameters.get("campaign_objective") or seed_parameters.get("campaign_type"),
        "target_segment":       seed_parameters.get("target_segment"),
        "creative_type":        seed_parameters.get("creative_type"),
        "target_audience_size": seed_parameters.get("target_audience_size") or seed_parameters.get("audience_size"),
        "budget_range":         seed_parameters.get("budget_range"),
        "baseline_history":     seed_parameters.get("baseline_history", True),
    }


def _compute_validation_score(stats_report: list) -> float:
    """
    Derive a single composite validation_score (0.0–1.0) from the per-industry
    statistical report.

    Formula:
        mean_deviation = average of |actual - target| / target  across all
                         (industry × metric) pairs.
        validation_score = max(0.0, round(1.0 - mean_deviation, 4))

    A score of 1.0 means the generated data perfectly matches benchmarks.
    A score of 0.90 means the aggregate drift is 10% across all metrics.
    """
    if not stats_report:
        return 0.0

    deviations = []
    for row in stats_report:
        for _metric, vals in row["metrics"].items():
            deviations.append(vals["deviation"])

    mean_deviation = sum(deviations) / len(deviations) if deviations else 0.0
    return max(0.0, round(1.0 - mean_deviation, 4))


def _rollup_ltv(customers: list, events: list) -> None:
    """
    Referential Integrity Roll-up (LTV Paradox Fix):
    Aggregate actual conversion revenue into each customer profile.
    Mutates customers in-place.
    """
    customer_lookup = {c["customer_id"]: c for c in customers}

    for evt in events:
        if evt["event_type"] == "conversion" and evt["customer_id"] is not None:
            cust = customer_lookup.get(evt["customer_id"])
            if cust:
                cust["total_spend_to_date"] = round(
                    cust["total_spend_to_date"] + evt["revenue"], 2
                )
                evt_date = evt["timestamp"][:10]
                if cust["last_purchase_date"] is None or evt_date > cust["last_purchase_date"]:
                    cust["last_purchase_date"] = evt_date


def generate_synthetic_data(
    industry: str,
    dataset_type: str = "all",
    volume: int = 100,
    seed_parameters: Optional[dict] = None,
    num_campaigns: Optional[int] = None,
    max_events_per_campaign: int = 200,
    output_format: str = "dict",
) -> dict:
    """
    Generate synthetic marketing data for a given industry and dataset type.

    Parameters
    ----------
    industry : str
        Target vertical. One of: "bfsi", "insurance", "rcg", "travel",
        "healthcare", "manufacturing".

    dataset_type : str
        Which dataset(s) to generate. One of:
            "customer_profiles"  — customer RFM + demographic records only
            "campaign_logs"      — campaign attribute + metric records only
            "engagement_events"  — timestamped event stream (requires campaigns)
            "all"                — all three datasets (default)

    volume : int
        Number of PRIMARY records to generate.
        • For "customer_profiles": number of customer records.
        • For "campaign_logs" / "all": number of campaigns (customers default
          to volume * 5 to give a realistic audience pool).
        • For "engagement_events": requires campaign generation; volume is
          treated as number of campaigns.

    seed_parameters : dict, optional
        Run-scoped overrides (never written to disk). Supported keys:
            target_ctr             (float)      — e.g. 0.025
            target_cpc             (float, INR) — e.g. 45.0
            target_conversion_rate (float)      — e.g. 0.03
            avg_ctr_range          (list[float]) — e.g. [0.015, 0.035]
            date_range             (list[str])   — e.g. ["2026-01-01", "2026-06-30"]
            target_channels        (list[str])   — e.g. ["Meta", "LinkedIn", "Instagram"]

    num_campaigns : int, optional
        Explicit campaign count override when dataset_type is "all".
        Defaults to max(1, volume // 10).

    max_events_per_campaign : int
        Hard cap on events written per campaign (memory guard).
        Default: 200. Increase for richer event datasets.

    output_format : str
        "dict"      — returns Python list-of-dicts (default, fastest)
        "json"      — returns JSON-serializable list-of-dicts (same as dict)
        "dataframe" — returns pandas DataFrame (requires pandas)

    Returns
    -------
    dict with keys:
        synthetic_dataset  : list[dict] | dict[str, list[dict]] | DataFrame
            • Single dataset type → flat list of records
            • "all"              → {"customers": [...], "campaigns": [...], "events": [...]}
        generation_report  : dict
            Metadata: parameters, record counts, per-industry stat deviations.
        validation_score   : float
            Composite statistical similarity score (0.0–1.0).
            1.0 = perfect benchmark alignment; < 0.85 = investigate drift.
        schema_validation  : dict
            Per-dataset schema pass/fail and message.

    Raises
    ------
    ValueError
        If `industry` or `dataset_type` are invalid.
    """

    # --- Input validation ---
    industry = industry.lower().strip()
    if industry not in VALID_INDUSTRIES:
        raise ValueError(
            f"Invalid industry '{industry}'. Must be one of: {sorted(VALID_INDUSTRIES)}"
        )

    valid_types = {"customer_profiles", "campaign_logs", "engagement_events", "all"}
    if dataset_type not in valid_types:
        raise ValueError(
            f"Invalid dataset_type '{dataset_type}'. Must be one of: {sorted(valid_types)}"
        )

    if volume < 1:
        raise ValueError(f"volume must be >= 1, got {volume}")

    # --- Load + patch configs ---
    profiles, rules = _load_configs()
    profiles = _apply_seed_parameters(profiles, industry, seed_parameters or {})

    # Phase 2: extract generation-control params from seed_parameters
    gen_params = _extract_generation_params(seed_parameters or {})

    # --- Volume logic ---
    if dataset_type == "customer_profiles":
        n_customers = volume
        n_campaigns = 0
    elif dataset_type == "campaign_logs":
        n_customers = 0
        n_campaigns = volume
    elif dataset_type == "engagement_events":
        # Events need campaigns as a prerequisite
        n_customers = max(10, volume * 5)
        n_campaigns = volume
    else:  # "all"
        n_campaigns = num_campaigns if num_campaigns is not None else max(1, volume // 10)
        n_customers = volume

    # --- Generate datasets ---
    customers = []
    campaigns = []
    events    = []
    stats_report = []
    schema_results = {}

    # 1. Customer Profiles
    if n_customers > 0:
        customers = generate_customer_profiles(
            industry=industry,
            volume=n_customers,
            start_id=1,
            baseline_history=gen_params["baseline_history"],
        )

    # 2. Campaign Logs
    if n_campaigns > 0:
        campaigns = generate_campaign_logs(
            industry=industry,
            volume=n_campaigns,
            start_id=1,
            date_range=gen_params["date_range"],
            target_channels=gen_params["target_channels"],
            campaign_objective=gen_params["campaign_objective"],
            target_segment=gen_params["target_segment"],
            creative_type=gen_params["creative_type"],
            target_audience_size=gen_params["target_audience_size"],
            budget_range=gen_params["budget_range"],
        )

    # 3. Engagement Events (requires campaigns)
    # NOTE: campaign_logs dataset_type also needs a brief event pass to stamp
    # reach/impressions/clicks/conversions/spend/cpm/cpl onto each campaign record.
    # Without this, campaign records are missing required schema fields.
    needs_events = dataset_type in ("engagement_events", "all", "campaign_logs")
    if dataset_type in ("engagement_events", "all") and campaigns:
        # Need at least a minimal customer pool for event attribution
        if not customers:
            customers = generate_customer_profiles(
                industry=industry,
                volume=max(10, n_campaigns * 5),
                start_id=1,
                baseline_history=gen_params["baseline_history"],
            )

        events = generate_engagement_events(
            campaigns, customers, profiles, rules,
            max_events_per_campaign=max_events_per_campaign
        )

        # LTV roll-up: referential integrity
        _rollup_ltv(customers, events)

        # Phase 3: Churn label stamping (must run AFTER LTV rollup
        # so last_purchase_date and total_spend_to_date are populated)
        compute_churn_labels(customers, events)
        churn_summary = get_churn_summary(customers)

        # Statistical validation (needs events)
        stats_report = validate_statistics(campaigns, events, profiles)

    elif dataset_type == "campaign_logs" and campaigns:
        # For campaign_logs-only requests, we still need to run the physics engine
        # to stamp reach/impressions/clicks/conversions/spend/cpm/cpl onto campaigns.
        # We generate a minimal internal customer pool just for event attribution,
        # but only return the campaign records (not the events or customers).
        _internal_customers = generate_customer_profiles(
            industry=industry, volume=max(10, n_campaigns * 5), start_id=1, baseline_history=False
        )
        _internal_events = generate_engagement_events(
            campaigns, _internal_customers, profiles, rules,
            max_events_per_campaign=max(50, min(max_events_per_campaign, 200))
        )
        stats_report = validate_statistics(campaigns, _internal_events, profiles)

    # Phase 3: churn labels for customer_profiles-only requests
    # (for "all" and "engagement_events", churn was already computed above)
    if dataset_type == "customer_profiles" and customers:
        compute_churn_labels(customers, events=[])

    # Build churn summary for generation report (only when customers were generated)
    churn_summary = get_churn_summary(customers) if customers else {}

    # 4. Schema Validation
    schema_map = {
        "customer_profiles": (customers, "customer_profiles.schema.json"),
        "campaign_logs":     (campaigns, "campaign_logs.schema.json"),
        "engagement_events": (events,    "engagement_events.schema.json"),
    }

    for ds_name, (records, schema_file) in schema_map.items():
        if records:
            ok, msg = validate_schema(records, os.path.join(_SCHEMA_DIR, schema_file))
            schema_results[ds_name] = {"passed": ok, "message": msg}
        else:
            schema_results[ds_name] = {"passed": None, "message": "Not generated"}

    # 5. Composite validation score (Phase 4: benchmark + correlation + distribution shape)
    validation_score, validation_details = compute_comprehensive_validation(
        campaigns=campaigns,
        events=events,
        customers=customers,
        profiles=profiles,
        industry=industry,
    )

    # 6. Generation report
    generation_report = {
        "parameters": {
            "industry":                industry,
            "dataset_type":            dataset_type,
            "volume":                  volume,
            "seed_parameters":         seed_parameters or {},
            "max_events_per_campaign": max_events_per_campaign,
        },
        "volumes": {
            "customers_generated": len(customers),
            "campaigns_generated": len(campaigns),
            "events_generated":    len(events),
        },
        "statistical_validation": validation_details.get("benchmark_metrics", stats_report),
        "validation_details":     validation_details,  # Phase 4 comprehensive report
        "churn_summary":          churn_summary,       # Phase 3 churn distribution
    }

    # 7. Build synthetic_dataset output
    if dataset_type == "customer_profiles":
        raw_dataset = customers
    elif dataset_type == "campaign_logs":
        raw_dataset = campaigns
    elif dataset_type == "engagement_events":
        raw_dataset = events
    else:  # "all"
        raw_dataset = {
            "customers": customers,
            "campaigns": campaigns,
            "events":    events,
        }

    # 8. Output format conversion
    if output_format == "dataframe":
        try:
            import pandas as pd
            if isinstance(raw_dataset, dict):
                synthetic_dataset = {k: pd.DataFrame(v) for k, v in raw_dataset.items()}
            else:
                synthetic_dataset = pd.DataFrame(raw_dataset)
        except ImportError:
            raise ImportError(
                "output_format='dataframe' requires pandas. "
                "Install it with: pip install pandas"
            )
    else:
        # "dict" and "json" are identical at the Python level
        synthetic_dataset = raw_dataset

    return {
        "synthetic_dataset":  synthetic_dataset,
        "generation_report":  generation_report,
        "validation_score":   validation_score,
        "schema_validation":  schema_results,
    }


# ---------------------------------------------------------------
# Multi-industry batch helper
# ---------------------------------------------------------------
def generate_batch(
    industries: list,
    dataset_type: str = "all",
    volume_per_industry: int = 100,
    seed_parameters: Optional[dict] = None,
    **kwargs
) -> dict:
    """
    Generate synthetic data for multiple industries in one call.

    Returns a dict keyed by industry, each value being a generate_synthetic_data() result.

    Example:
        results = generate_batch(
            industries=["bfsi", "rcg", "manufacturing"],
            dataset_type="campaign_logs",
            volume_per_industry=200
        )
        bfsi_campaigns = results["bfsi"]["synthetic_dataset"]
    """
    results = {}
    for ind in industries:
        results[ind] = generate_synthetic_data(
            industry=ind,
            dataset_type=dataset_type,
            volume=volume_per_industry,
            seed_parameters=seed_parameters,
            **kwargs,
        )
    return results
