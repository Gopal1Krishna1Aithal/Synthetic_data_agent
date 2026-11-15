# Synthetic Data Agent (Agent 2)
### Marketing Intelligence Multi-Agent Suite

A production-grade, mathematically grounded synthetic data generation engine simulating realistic multi-vertical digital marketing ecosystems. Built specifically as **Agent 2** in the autonomous 8-Agent Marketing Intelligence Suite to feed downstream Machine Learning agents with privacy-safe, statistically representative data.

---

## 🎯 System Role & Downstream Integration

Agent 2 serves as the ground-truth data factory for the entire marketing intelligence platform:

| Downstream Agent | Primary Dataset Consumed | Key Features Provided | Business / ML Purpose |
| :--- | :--- | :--- | :--- |
| **Agent 4: Campaign Performance Predictor** | `campaign_logs` | `reach`, `impressions`, `clicks`, `conversions`, `spend`, `cpm`, `cpl` | Multi-objective regression models to forecast campaign efficacy prior to ad spend. |
| **Agent 3: Budget Allocator** | `campaign_logs`, `engagement_events` | `channel`, `budget`, diminishing returns, CPC benchmarks | Media mix optimization, channel saturation modeling, and budget re-allocation. |
| **Agent 6: Predictive Churn & Engagement** | `customer_profiles`, `engagement_events` | `is_churned`, `churn_risk_tier`, `top_drivers`, `days_since_last_purchase`, `purchase_frequency`, RFM stream | Supervised churn classification, survival analysis, and automated retention trigger discovery. |
| **Agent 5: Marketing Optimization Orchestrator** | All datasets | Cross-vertical state tables, real-time batch simulations | End-to-end autonomous closed-loop campaign orchestration. |
| **Agent 8: Governance & Guardrails** | Data Schemas & Identifiers | Zero real customer PII, synthetic IDs (`CUST-XXXXX`, `CAMP-XXXXX`), Draft-7 schemas | Compliance audits, privacy guarantees, schema validation. |

---

## 📂 Project Architecture

```text
synthetic-data-agent/
|-- core.py                         # Canonical Python API (generate_synthetic_data, generate_batch)
|-- server.py                       # REST API microservice (Flask-based HTTP server)
|-- api.py                          # CLI wrapper for local executions and presets
|-- churn_labels.py                 # Ground-truth churn simulation engine for Agent 6
|-- validation.py                   # Statistical validation engine (benchmark deviations, correlations, TVD)
|-- relationships.py                # Marketing physics engine (saturation, multipliers, attribution delays)
|-- config/
|   |-- industry_profiles.json      # Vertical benchmarks (CPC, CTR, CVR, budget ranges)
|   |-- relationship_rules.json     # Behavioral rules (creative type, audience, channel boosts)
|-- generators/
|   |-- campaign_logs_gen.py        # Campaign generator with targeted seed overrides
|   |-- customer_profiles_gen.py    # Customer generator with baseline RFM histories
|   |-- engagement_events_gen.py    # Funnel event simulator (impressions -> clicks -> conversions)
|-- schemas/                        # JSON Draft-7 schemas with strict typing
|   |-- campaign_logs.schema.json
|   |-- customer_profiles.schema.json
|   |-- engagement_events.schema.json
|-- tests/
|   |-- test_referential_integrity.py  # 23-test automated regression & integrity suite
|-- outputs/                        # Default output directory for generated deliverables
```

---

## ⚡ Core Capabilities

1. **Six Industry Verticals:** `bfsi`, `insurance`, `rcg` (Retail/CPG), `travel`, `healthcare`, and `manufacturing`.
2. **Referential Integrity & Zero PII:** Zero orphan foreign keys. All customer and campaign references resolve. Customer LTV matches conversion event revenues with mathematical precision. All identifiers are synthetic tokens.
3. **Targeted Generation:** Generate only the datasets required (`campaign_logs`, `customer_profiles`, `engagement_events`, or `all`).
4. **Seed Parameter Overrides:** Fine-grained simulation controls:
   - `date_range`: Explicit temporal bounds for campaigns (e.g. `["2026-03-01", "2026-05-31"]`).
   - `target_channels`: Restrict generation to specific channels (e.g. `["Meta", "Instagram"]`).
   - `campaign_objective`, `target_segment`, `creative_type`, `target_audience_size`, `budget_range`.
   - `baseline_history`: Generates pre-existing RFM tenure and spend for cold-start churn analysis.
5. **Ground-Truth Churn Modeling:** Computes `days_since_last_purchase`, `purchase_frequency`, `churn_risk_tier` (`Low | Medium | High`), `is_churned` (`bool`), and explainable `top_drivers` (e.g. `inactivity_197_days_exceeds_threshold`).
6. **Comprehensive Statistical Validation:** Automatically calculates benchmark metric deviations, correlation sanity ($r_{\text{budget},\text{impressions}} > 0$, CPC channel order), and distribution shape analysis, returning a bounded composite `validation_score` (0.0 to 1.0).
7. **Multiple Consumption Modes:**
   - Importable Python module (`core.py`) returning dicts or Pandas DataFrames.
   - HTTP REST server (`server.py`) for inter-agent network calls.
   - CLI tool (`api.py`) for batch runs and specialized presets.

---

## 🚀 Quickstart & Usage

### 1. Python Library Integration (Recommended for Agents 3, 4, 6)

```python
from core import generate_synthetic_data, generate_batch

# Generate a targeted campaign dataset for Agent 4
result = generate_synthetic_data(
    industry="bfsi",
    dataset_type="campaign_logs",
    num_campaigns=50,
    seed_parameters={
        "date_range": ["2026-01-01", "2026-06-30"],
        "target_channels": ["LinkedIn", "Google Search"]
    },
    output_format="dataframe"  # Returns pandas.DataFrame directly
)
campaigns_df = result["synthetic_dataset"]
print(f"Validation score: {result['validation_score']:.4f}")
print(campaigns_df.head())

# Batch generate multiple verticals
batch_results = generate_batch(
    industries=["rcg", "travel"],
    num_customers=200,
    num_campaigns=20
)
```

### 2. HTTP REST Service

Start the microservice:
```bash
python server.py
# Running on http://127.0.0.1:5000
```

#### Endpoints:
- `GET /health`: Liveness probe.
- `GET /industries`: Returns supported verticals and available channels.
- `POST /generate`: Generates synthetic data for a specified vertical.
  ```json
  // Request Body
  {
    "industry": "rcg",
    "dataset_type": "customer_profiles",
    "num_customers": 100,
    "seed_parameters": {
      "baseline_history": true
    }
  }
  ```
- `POST /generate/batch`: Generates multiple verticals in parallel.

### 3. CLI Tool & Intern Team Presets

```bash
# Full generation across all 6 verticals
python api.py --preset full --output-dir outputs

# Agent 6 Preset: Churn features with RFM metrics
python api.py --industries rcg --num-customers 500 --preset churn --output-dir outputs/rcg_churn

# Agent 4 Preset: Stamped campaign performance metrics
python api.py --industries manufacturing --num-campaigns 100 --preset campaign-performance --output-dir outputs/mfg_performance

# Agent 3 Preset: Channel attribution & spend benchmarks
python api.py --industries bfsi --num-campaigns 50 --preset channel --output-dir outputs/bfsi_channel

# Export to CSV format for direct analysis
python api.py --output-format csv --output-dir outputs/csv_export
```

---

## 🧪 Automated Test Suite

Run the full 23-test regression and mathematical validation suite:

```bash
python tests/test_referential_integrity.py
```

### Verified Test Cases:
1. **Test 1:** Referential integrity (zero orphaned customer or campaign IDs across events).
2. **Test 2:** LTV rollup accuracy (profile spend matches conversion event revenues).
3. **Test 3:** JSON Schema validation against Draft-7 specifications.
4. **Test 4:** Composite statistical validation score bounds and drift tolerances.
5. **Test 5:** Standalone targeted dataset generation (`campaign_logs`, `customer_profiles`).
6. **Test 6:** Generation report schema and metadata verification.
7. **Test 7:** Seed parameters pass-through.
8. **Test 8:** Multi-vertical batch generation.
9. **Test 9:** Temporal bounds verification (`date_range`).
10. **Test 10:** Channel isolation verification (`target_channels`).
11. **Test 11:** Ground-truth churn fields existence and typing.
12. **Test 12:** Consistency between `is_churned` and `churn_risk_tier`.
13. **Test 13:** Never-purchased cohort high-risk assignment.
14. **Test 14:** `churn_summary` generation report metrics.
15. **Test 15:** Draft-7 JSON schema compliance with churn attributes.
16. **Test 16:** Conversion event purchase frequency incrementing.
17. **Test 17:** Campaign parameter override controls (`objective`, `segment`, `creative`).
18. **Test 18:** Vertical churn distribution bounds (10% to 60%).
19. **Test 19:** Statistical correlation sanity ($r_{\text{budget},\text{impressions}} > 0$).
20. **Test 20:** Customer demographic and RFM distribution stability.
21. **Test 21:** Complete 6-industry generation coverage.
22. **Test 22:** HTTP REST API endpoint functionality (`/health`, `/industries`, `/generate`).
23. **Test 23:** Output format flexibility (dict and Pandas DataFrame).

---

## 🛡️ Privacy & Compliance
- **Zero Real PII:** No actual customer names, phone numbers, or credit card numbers are collected or emitted.
- **Synthesized Tokens:** Synthetic emails adhere to `@example.com` domains.
- **Privacy Standard:** Meets GDPR, CCPA, and DPDP requirements for synthetic data exchange across enterprise multi-agent architectures.
