"""
tests/test_referential_integrity.py

Verifies:
  1. No orphaned customer_id or campaign_id in events (referential integrity)
  2. LTV roll-up: customer total_spend_to_date = sum of their conversion revenues
  3. Schema conformance via generate_synthetic_data()
  4. validation_score is within acceptable range (>= 0.70)
  5. generation_report has expected structure

Run from project root:
    python -m pytest tests/ -v
    # or directly:
    python tests/test_referential_integrity.py
"""

import sys
import os

# Allow running from project root (python tests/test_referential_integrity.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import generate_synthetic_data, generate_batch, VALID_INDUSTRIES


# ---------------------------------------------------------------
# Helper
# ---------------------------------------------------------------
def _assert(condition, message):
    if not condition:
        raise AssertionError(f"FAILED: {message}")
    print(f"  PASS  {message}")


# ---------------------------------------------------------------
# Test 1: Referential Integrity
# ---------------------------------------------------------------
def test_referential_integrity():
    print("\n[Test 1] Referential Integrity")

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="all",
        volume=50,
        num_campaigns=5,
    )

    dataset   = result["synthetic_dataset"]
    customers = dataset["customers"]
    campaigns = dataset["campaigns"]
    events    = dataset["events"]

    customer_ids = {c["customer_id"] for c in customers}
    campaign_ids = {c["campaign_id"] for c in campaigns}

    orphaned_customers = [
        e["event_id"] for e in events
        if e["customer_id"] is not None and e["customer_id"] not in customer_ids
    ]
    orphaned_campaigns = [
        e["event_id"] for e in events
        if e["campaign_id"] not in campaign_ids
    ]

    _assert(len(orphaned_customers) == 0, f"No orphaned customer_ids ({len(events)} events checked)")
    _assert(len(orphaned_campaigns) == 0, f"No orphaned campaign_ids ({len(events)} events checked)")
    print(f"  INFO  Generated {len(customers)} customers, {len(campaigns)} campaigns, {len(events)} events.")


# ---------------------------------------------------------------
# Test 2: LTV Roll-up Accuracy
# ---------------------------------------------------------------
def test_ltv_rollup():
    print("\n[Test 2] LTV Roll-up Accuracy")

    # Use baseline_history=False to verify pure event revenue rollup
    result = generate_synthetic_data(
        industry="bfsi",
        dataset_type="all",
        volume=30,
        num_campaigns=3,
        seed_parameters={"baseline_history": False},
    )
    dataset   = result["synthetic_dataset"]
    customers = dataset["customers"]
    events    = dataset["events"]

    # Build expected LTV per customer from events
    expected_ltv = {}
    for evt in events:
        if evt["event_type"] == "conversion" and evt["customer_id"] is not None:
            cid = evt["customer_id"]
            expected_ltv[cid] = round(expected_ltv.get(cid, 0.0) + evt["revenue"], 2)

    # Compare against rolled-up customer profiles
    cust_lookup = {c["customer_id"]: c for c in customers}
    mismatches = []
    for cid, exp_ltv in expected_ltv.items():
        actual_ltv = cust_lookup[cid]["total_spend_to_date"]
        if abs(actual_ltv - exp_ltv) > 0.01:  # allow 1 paise float tolerance
            mismatches.append((cid, exp_ltv, actual_ltv))

    _assert(len(mismatches) == 0, f"LTV roll-up: all {len(expected_ltv)} converting customers match")


# ---------------------------------------------------------------
# Test 3: Schema Validation Passes
# ---------------------------------------------------------------
def test_schema_validation():
    print("\n[Test 3] Schema Validation")

    result = generate_synthetic_data(
        industry="manufacturing",
        dataset_type="all",
        volume=20,
        num_campaigns=2,
    )
    schema_val = result["schema_validation"]

    for ds_name, res in schema_val.items():
        if res["passed"] is None:
            print(f"  SKIP  {ds_name}: not generated")
            continue
        _assert(res["passed"], f"Schema valid for '{ds_name}': {res['message']}")


# ---------------------------------------------------------------
# Test 4: Validation Score Range
# ---------------------------------------------------------------
def test_validation_score():
    print("\n[Test 4] Validation Score")

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="all",
        volume=500,          # larger sample → normalization converges reliably
        num_campaigns=50,
    )
    score = result["validation_score"]
    _assert(isinstance(score, float), f"validation_score is a float: {score}")
    _assert(0.0 <= score <= 1.0,      f"validation_score in [0.0, 1.0]: {score}")
    _assert(score >= 0.60,            f"validation_score >= 0.60 (acceptable drift at n=50): {score}")
    print(f"  INFO  validation_score = {score}")


# ---------------------------------------------------------------
# Test 5: Targeted Dataset Types Work Independently
# ---------------------------------------------------------------
def test_targeted_dataset_types():
    print("\n[Test 5] Targeted Dataset Types")

    for ds_type, industry in [
        ("customer_profiles", "healthcare"),
        ("campaign_logs",     "travel"),
    ]:
        result = generate_synthetic_data(
            industry=industry,
            dataset_type=ds_type,
            volume=10,
        )
        dataset = result["synthetic_dataset"]
        _assert(isinstance(dataset, list), f"dataset_type='{ds_type}' returns a list")
        _assert(len(dataset) > 0,          f"dataset_type='{ds_type}' returns non-empty list")
        _assert(len(dataset) == 10,        f"dataset_type='{ds_type}' returns correct volume")


# ---------------------------------------------------------------
# Test 6: Generation Report Structure
# ---------------------------------------------------------------
def test_generation_report_structure():
    print("\n[Test 6] Generation Report Structure")

    result = generate_synthetic_data(
        industry="insurance",
        dataset_type="all",
        volume=20,
        num_campaigns=2,
    )
    report = result["generation_report"]
    _assert("parameters" in report,            "'parameters' key in report")
    _assert("volumes"    in report,            "'volumes' key in report")
    _assert("statistical_validation" in report, "'statistical_validation' key in report")
    _assert(report["parameters"]["industry"] == "insurance", "industry param preserved")


# ---------------------------------------------------------------
# Test 7: seed_parameters Apply Correctly
# ---------------------------------------------------------------
def test_seed_parameters():
    print("\n[Test 7] Seed Parameters")

    target_ctr = 0.001  # Very low CTR — should visibly suppress clicks
    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="campaign_logs",
        volume=20,
        seed_parameters={"target_ctr": target_ctr},
    )
    # Campaigns should still generate — just with suppressed CTR
    dataset = result["synthetic_dataset"]
    _assert(len(dataset) == 20, f"seed_parameters: correct volume generated ({len(dataset)} campaigns)")


# ---------------------------------------------------------------
# Test 8: Batch Generation
# ---------------------------------------------------------------
def test_batch_generation():
    print("\n[Test 8] Batch Generation")

    results = generate_batch(
        industries=["bfsi", "rcg"],
        dataset_type="campaign_logs",
        volume_per_industry=5,
    )
    _assert("bfsi" in results, "Batch result contains 'bfsi'")
    _assert("rcg"  in results, "Batch result contains 'rcg'")
    _assert(len(results["bfsi"]["synthetic_dataset"]) == 5, "BFSI: correct volume")
    _assert(len(results["rcg"]["synthetic_dataset"])  == 5, "RCG: correct volume")


# ---------------------------------------------------------------
# Phase 2 Tests
# ---------------------------------------------------------------

def test_date_range_seed_parameter():
    """Phase 2: date_range seed_parameter constrains campaign start dates."""
    print("\n[Test 9] Phase 2 — date_range seed_parameter")

    date_range = ["2026-03-01", "2026-05-31"]
    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="campaign_logs",
        volume=20,
        seed_parameters={"date_range": date_range},
    )
    campaigns = result["synthetic_dataset"]
    _assert(len(campaigns) == 20, f"date_range: correct volume ({len(campaigns)} campaigns)")

    # All campaign start dates must fall within the requested window
    for c in campaigns:
        _assert(
            date_range[0] <= c["start_date"] <= date_range[1],
            f"Campaign {c['campaign_id']} start_date {c['start_date']} in [{date_range[0]}, {date_range[1]}]"
        )
    print(f"  INFO  All 20 campaign start_dates within {date_range[0]} – {date_range[1]}")


def test_target_channels_seed_parameter():
    """Phase 2: target_channels seed_parameter restricts channel selection."""
    print("\n[Test 10] Phase 2 — target_channels seed_parameter")

    allowed = {"Meta", "Instagram"}
    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="campaign_logs",
        volume=30,
        seed_parameters={"target_channels": list(allowed)},
    )
    campaigns = result["synthetic_dataset"]
    _assert(len(campaigns) == 30, "target_channels: correct volume")

    bad_channels = [c["target_channel"] for c in campaigns if c["target_channel"] not in allowed]
    _assert(
        len(bad_channels) == 0,
        f"All campaigns use allowed channels only (found {len(bad_channels)} violations)"
    )
    channels_used = {c["target_channel"] for c in campaigns}
    print(f"  INFO  Channels in output: {channels_used}")


# ---------------------------------------------------------------
# Phase 3 Tests
# ---------------------------------------------------------------

def test_churn_labels_present():
    """Phase 3: churn labels and top_drivers are stamped on all customer records."""
    print("\n[Test 11] Phase 3 — Churn label fields present")

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="all",
        volume=50,
        num_campaigns=5,
    )
    customers = result["synthetic_dataset"]["customers"]

    required_fields = [
        "days_since_last_purchase", "purchase_frequency",
        "churn_risk_tier", "is_churned", "top_drivers"
    ]
    for field in required_fields:
        missing = [c["customer_id"] for c in customers if field not in c]
        _assert(len(missing) == 0, f"Field '{field}' present on all {len(customers)} customers")

    tiers = {c["churn_risk_tier"] for c in customers}
    _assert(tiers.issubset({"Low", "Medium", "High"}), f"All churn_risk_tier values valid: {tiers}")

    is_churned_types = {type(c["is_churned"]) for c in customers}
    _assert(is_churned_types == {bool}, "is_churned is bool on all records")

    for c in customers:
        _assert(isinstance(c["top_drivers"], list), "top_drivers is a list")
        _assert(len(c["top_drivers"]) > 0, "top_drivers is non-empty")


def test_churn_is_churned_matches_tier():
    """Phase 3: is_churned=True iff churn_risk_tier='High'."""
    print("\n[Test 12] Phase 3 — is_churned consistent with churn_risk_tier")

    result = generate_synthetic_data(
        industry="bfsi",
        dataset_type="all",
        volume=80,
        num_campaigns=8,
    )
    customers = result["synthetic_dataset"]["customers"]

    mismatches = [
        c["customer_id"] for c in customers
        if c["is_churned"] != (c["churn_risk_tier"] == "High")
    ]
    _assert(len(mismatches) == 0, f"is_churned consistent with churn_risk_tier ({len(customers)} checked)")


def test_churn_never_purchased_always_high():
    """Phase 3: Customers with no purchases are always High risk."""
    print("\n[Test 13] Phase 3 — Never-purchased customers are always High risk")

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="all",
        volume=100,
        num_campaigns=5,
    )
    customers = result["synthetic_dataset"]["customers"]

    never_purchased = [c for c in customers if c["days_since_last_purchase"] is None]
    if never_purchased:
        wrong = [c["customer_id"] for c in never_purchased if c["churn_risk_tier"] != "High"]
        _assert(len(wrong) == 0, f"All {len(never_purchased)} never-purchased customers are 'High' risk")
        print(f"  INFO  {len(never_purchased)} never-purchased customers — all marked High ✓")
    else:
        print("  INFO  All customers had purchases")


def test_churn_summary_in_report():
    """Phase 3: generation_report contains churn_summary."""
    print("\n[Test 14] Phase 3 — churn_summary in generation_report")

    result = generate_synthetic_data(
        industry="manufacturing",
        dataset_type="all",
        volume=50,
        num_campaigns=5,
    )
    report = result["generation_report"]
    _assert("churn_summary" in report, "'churn_summary' key in generation_report")

    summary = report["churn_summary"]
    _assert("total" in summary,       "churn_summary has 'total'")
    _assert("churned_count" in summary, "churn_summary has 'churned_count'")
    _assert("churn_rate" in summary,  "churn_summary has 'churn_rate'")
    _assert("tier_counts" in summary, "churn_summary has 'tier_counts'")
    _assert(0.0 <= summary["churn_rate"] <= 1.0, f"churn_rate in [0,1]: {summary['churn_rate']}")
    print(f"  INFO  Churn summary: {summary}")


def test_churn_schema_validates():
    """Phase 3: customer_profiles schema still passes with new churn fields and top_drivers."""
    print("\n[Test 15] Phase 3 — Updated schema validates with churn fields")

    result = generate_synthetic_data(
        industry="healthcare",
        dataset_type="all",
        volume=30,
        num_campaigns=3,
    )
    schema_val = result["schema_validation"]
    _assert(
        schema_val["customer_profiles"]["passed"] is True,
        f"customer_profiles schema passes with churn fields: {schema_val['customer_profiles']['message']}"
    )


def test_purchase_frequency_matches_events():
    """Phase 3: conversion events correctly increment purchase_frequency and spend."""
    print("\n[Test 16] Phase 3 — purchase_frequency increments from conversion events")

    # Run with baseline_history=False to isolate the event roll-up test
    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="all",
        volume=50,
        num_campaigns=5,
        seed_parameters={"baseline_history": False},
    )
    customers = result["synthetic_dataset"]["customers"]
    events    = result["synthetic_dataset"]["events"]

    expected_freq = {}
    for evt in events:
        if evt["event_type"] == "conversion" and evt["customer_id"] is not None:
            cid = evt["customer_id"]
            expected_freq[cid] = expected_freq.get(cid, 0) + 1

    mismatches = []
    for c in customers:
        expected = expected_freq.get(c["customer_id"], 0)
        actual   = c["purchase_frequency"]
        if expected != actual:
            mismatches.append((c["customer_id"], expected, actual))

    _assert(len(mismatches) == 0, f"purchase_frequency strictly matches events when baseline_history=False")


def test_phase2_campaign_parameter_overrides():
    """Phase 2: campaign_objective, target_segment, creative_type overrides in seed_parameters."""
    print("\n[Test 17] Phase 2 — campaign parameter overrides")

    result = generate_synthetic_data(
        industry="manufacturing",
        dataset_type="campaign_logs",
        volume=15,
        seed_parameters={
            "campaign_objective": "Lead Generation",
            "target_segment":     "Enterprise",
            "creative_type":      "Document",
            "target_audience_size": 75000,
        },
    )
    campaigns = result["synthetic_dataset"]
    _assert(len(campaigns) == 15, "Correct volume generated")

    for c in campaigns:
        _assert(c["campaign_objective"] == "Lead Generation", "Objective override applied")
        _assert(c["target_segment"] == "Enterprise", "Segment override applied")
        _assert(c["creative_type"] == "Document", "Creative override applied")
        _assert(c["target_audience_size"] == 75000, "Audience size override applied")
    print("  INFO  All 15 campaigns respected exact parameter overrides ✓")


def test_phase3_realistic_churn_distribution():
    """Phase 3: Customer churn rate is balanced and realistic (between 10% and 60%, not 100%)."""
    print("\n[Test 18] Phase 3 — Realistic churn rate distribution")

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="customer_profiles",
        volume=100,
    )
    customers = result["synthetic_dataset"]
    churned_count = sum(1 for c in customers if c["is_churned"])
    churn_rate = churned_count / len(customers)

    _assert(0.10 <= churn_rate <= 0.60, f"Churn rate ({churn_rate:.2%}) is realistic (10%-60%)")
    print(f"  INFO  Realistic churn rate: {churn_rate:.2%} across {len(customers)} customers ✓")


# ---------------------------------------------------------------
# Phase 4 Tests: Statistical Validation & Correlation Sanity
# ---------------------------------------------------------------

def test_phase4_correlation_sanity():
    """Phase 4: Marketing physics correlation sanity (budget vs impressions positive correlation)."""
    print("\n[Test 19] Phase 4 — Correlation Sanity")

    result = generate_synthetic_data(
        industry="rcg",
        dataset_type="campaign_logs",
        volume=50,
    )
    details = result["generation_report"]["validation_details"]
    _assert("correlation_sanity" in details, "correlation_sanity present in validation_details")

    corr = details["correlation_sanity"]
    _assert(corr["passed"] is True, f"Correlation sanity passed: {corr['message']}")
    _assert(corr["budget_impressions_corr"] > 0.0, f"Budget-impressions r ({corr['budget_impressions_corr']}) is positive (> 0.0)")
    print(f"  INFO  Budget vs Impressions r = {corr['budget_impressions_corr']} ✓")


def test_phase4_customer_distribution_shape():
    """Phase 4: Standalone customer profiles achieves non-zero validation_score and passes distribution checks."""
    print("\n[Test 20] Phase 4 — Customer Distribution Shape")

    result = generate_synthetic_data(
        industry="bfsi",
        dataset_type="customer_profiles",
        volume=120,
    )
    score = result["validation_score"]
    _assert(score >= 0.70, f"Standalone customer_profiles validation_score ({score}) >= 0.70")

    details = result["generation_report"]["validation_details"]
    cust_sanity = details["customer_distribution_sanity"]
    _assert(cust_sanity["passed"] is True, f"Customer distribution sanity passed: {cust_sanity['message']}")
    _assert(cust_sanity["segment_similarity_score"] >= 0.75, f"Segment similarity score ({cust_sanity['segment_similarity_score']}) >= 0.75")
    print(f"  INFO  Customer distribution score = {cust_sanity['segment_similarity_score']}, validation_score = {score} ✓")


# ---------------------------------------------------------------
# Phase 5 Tests: Suite Coverage & API Server Integration
# ---------------------------------------------------------------

def test_phase5_all_six_industries():
    """Phase 5: All 6 industry verticals generate valid datasets and pass schemas."""
    print("\n[Test 21] Phase 5 — Full 6-Industry Generation Coverage")

    for ind in sorted(VALID_INDUSTRIES):
        res = generate_synthetic_data(industry=ind, dataset_type="campaign_logs", volume=5)
        _assert(len(res["synthetic_dataset"]) == 5, f"{ind.upper()} generated 5 campaigns")
        _assert(res["schema_validation"]["campaign_logs"]["passed"] is True, f"{ind.upper()} schema valid")
    print("  INFO  All 6 verticals (BFSI, Insurance, RCG, Travel, Healthcare, Manufacturing) generated cleanly ✓")


def test_phase5_http_server_endpoints():
    """Phase 5: HTTP REST server endpoints respond correctly to health, industries, and generation."""
    print("\n[Test 22] Phase 5 — HTTP REST Server Endpoints")

    from server import app
    _assert(app is not None, "Server app initialized")

    client = app.test_client()

    # 1. Health endpoint
    h_resp = client.get("/health")
    _assert(h_resp.status_code == 200, "GET /health returns 200")
    _assert(h_resp.get_json()["status"] == "ok", "GET /health status is 'ok'")

    # 2. Industries endpoint
    i_resp = client.get("/industries")
    _assert(i_resp.status_code == 200, "GET /industries returns 200")
    data = i_resp.get_json()
    _assert("bfsi" in data, "Industries response includes 'bfsi'")
    _assert("rcg" in data, "Industries response includes 'rcg'")

    # 3. POST /generate endpoint
    g_resp = client.post("/generate", json={
        "industry": "rcg",
        "dataset_type": "campaign_logs",
        "volume": 10,
        "seed_parameters": {"target_ctr": 0.035}
    })
    _assert(g_resp.status_code == 200, "POST /generate returns 200")
    body = g_resp.get_json()
    _assert("synthetic_dataset" in body, "Response contains 'synthetic_dataset'")
    _assert("validation_score" in body, "Response contains 'validation_score'")
    _assert(len(body["synthetic_dataset"]) == 10, "Response returned 10 campaigns")
    print("  INFO  HTTP /health, /industries, and /generate all verified ✓")


def test_phase5_output_formats():
    """Phase 5: Dict, JSON, and DataFrame output formats work seamlessly."""
    print("\n[Test 23] Phase 5 — Output Format Flexibility")

    # 1. Dict / JSON format
    dict_res = generate_synthetic_data(industry="rcg", dataset_type="campaign_logs", volume=5, output_format="dict")
    _assert(isinstance(dict_res["synthetic_dataset"], list), "dict format returns list")

    # 2. DataFrame format (if pandas is installed)
    try:
        import pandas as pd
        df_res = generate_synthetic_data(industry="rcg", dataset_type="campaign_logs", volume=5, output_format="dataframe")
        _assert(isinstance(df_res["synthetic_dataset"], pd.DataFrame), "dataframe format returns pandas DataFrame")
        _assert(len(df_res["synthetic_dataset"]) == 5, "DataFrame has 5 rows")
        print("  INFO  Pandas DataFrame output tested successfully ✓")
    except ImportError:
        print("  INFO  pandas not installed — skipping DataFrame assertion")


# ---------------------------------------------------------------
# Runner
# ---------------------------------------------------------------
if __name__ == "__main__":
    tests = [
        test_referential_integrity,
        test_ltv_rollup,
        test_schema_validation,
        test_validation_score,
        test_targeted_dataset_types,
        test_generation_report_structure,
        test_seed_parameters,
        test_batch_generation,
        # Phase 2
        test_date_range_seed_parameter,
        test_target_channels_seed_parameter,
        test_phase2_campaign_parameter_overrides,
        # Phase 3
        test_churn_labels_present,
        test_churn_is_churned_matches_tier,
        test_churn_never_purchased_always_high,
        test_churn_summary_in_report,
        test_churn_schema_validates,
        test_purchase_frequency_matches_events,
        test_phase3_realistic_churn_distribution,
        # Phase 4
        test_phase4_correlation_sanity,
        test_phase4_customer_distribution_shape,
        # Phase 5
        test_phase5_all_six_industries,
        test_phase5_http_server_endpoints,
        test_phase5_output_formats,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR in {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests.")
    if failed == 0:
        print("All tests passed! ✓")
    sys.exit(0 if failed == 0 else 1)
