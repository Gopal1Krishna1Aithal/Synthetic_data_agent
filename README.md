# Synthetic Data Agent

A highly advanced, mathematically rigorous synthetic data generation pipeline designed to simulate complex, multi-vertical digital marketing datasets. This project is purpose-built to act as the foundational training data for downstream Machine Learning models (such as Predictive Churn, Budget Allocators, and Campaign Performance predictors) in a privacy-safe, PII-free environment.

---

## 📂 Project Structure

```text
synthetic-data-agent/
|-- api.py                        # The main CLI entrypoint
|-- relationships.py              # Mathematical physics engine (normalization, multipliers)
|-- validation.py                 # JSON Schema and statistical validation logic
|-- LOGIC_EXPLANATION.md          # Read this to understand the ML-features and math logic
|-- README.md                     # This file
|
|-- config/                       
|   |-- industry_profiles.json    # Target macro-benchmarks (CPC, CTR) by vertical
|   |-- relationship_rules.json   # Multipliers (how video vs image affects CTR)
|
|-- generators/                   # Core generation logic
|   |-- campaign_logs_gen.py      # Generates campaigns based on industry rules
|   |-- customer_profiles_gen.py  # Generates PII-free customers via Faker
|   |-- engagement_events_gen.py  # Generates the millions of ad clicks/conversions
|
|-- schemas/                      # Strict JSON Schemas for validation
|   |-- campaign_logs.schema.json
|   |-- customer_profiles.schema.json
|   |-- engagement_events.schema.json
|
|-- tests/                        
|   |-- test_referential_integrity.py  # Tests LTV rollups and foreign key constraints
|
|-- outputs/                      # Default output directory for generated JSONs
```

---

## ⚙️ Data Flow & Architecture

The pipeline follows a strict generation order to ensure 100% mathematical referential integrity across the datasets:

1. **Macro Configuration Load:** The pipeline loads the industry benchmarks (`industry_profiles.json`) and the relationship multipliers (`relationship_rules.json`).
2. **Customer Initialization:** `customer_profiles_gen.py` generates realistic, PII-free profiles using the `Faker` library. **Crucially, customer Lifetime Value (LTV) is initialized to ₹0.**
3. **Campaign Generation:** `campaign_logs_gen.py` spawns ad campaigns. It mathematically determines target audiences, assigns budgets, and calculates expected costs based on the industry physics.
4. **Event Simulation:** `engagement_events_gen.py` unleashes the marketing physics engine:
    * It runs a `min(impressions, audience_size)` check to enforce Audience Saturation.
    * It applies Beta-distributed timestamps to mimic launch-day engagement spikes.
    * It applies a 0-7 day attribution delay for conversion events.
    * It simulates iOS 14 by masking 30% of top-of-funnel clicks with `customer_id: null`.
5. **LTV Roll-up (Integrity Check):** The main `api.py` loops back through the generated conversion events and aggregates the exact `revenue` into the respective user's `customer_profile`, ensuring the profile LTV matches the event log perfectly.
6. **Validation:** Every row is validated against the strict JSON schemas, and a statistical validation report is generated to prove the generated data didn't drift too far from the macro-benchmarks.
7. **Export:** Files are serialized to JSON or CSV based on the CLI input.

---

## 🚀 Usage Guide

The `api.py` exposes a robust CLI that allows you to instantly generate exactly what you need without bloating your hard drive.

### 1. Basic Generation (Default)
Generates a small dataset across all 6 verticals.
```bash
python api.py
```

### 2. Large Scale Generation
Control exactly how many profiles and campaigns you want.
```bash
python api.py --num-customers 1000 --num-campaigns 500
```

### 3. Vertical-Specific Generation
Only want data for the Travel and Healthcare verticals? 
```bash
python api.py --industries travel healthcare --num-customers 500
```

### 4. Output Formats (JSON vs CSV)
If your downstream Data Science teams prefer DataFrames, export to CSV.
```bash
python api.py --output-format csv --output-dir outputs_csv
```

### 5. Presets (Column Filtering)
If you are generating 3,000,000 events, you don't want massive files full of columns your ML model doesn't need. Use `--preset` to automatically filter the columns for specific intern teams:

* **Predictive Churn Agent:** Only outputs RFM features.
  ```bash
  python api.py --preset churn
  ```
* **Campaign Performance Agent:** Outputs only campaign objectives and stamped ML performance targets (`reach`, `impressions`, `cpm`).
  ```bash
  python api.py --preset campaign-performance
  ```
* **Channel Optimizer Agent:** Outputs only channel attribution features.
  ```bash
  python api.py --preset channel
  ```

### 6. The Dry Run (Schema Validation)
Want to verify your changes haven't broken the JSON schemas, but don't want to wait for files to write to disk? Run a dry-run. It caps events to 20 per campaign and does the math purely in memory.
```bash
python api.py --dry-run
```

---

## 📊 The Generation Report

Every successful run automatically writes a `generation_report.json` to your output directory. 

This file is critical for downstream ML Engineers. It contains:
1. The exact CLI parameters used to generate the run.
2. The total volume of rows generated.
3. A **Statistical Validation Report** showing the percentage deviation between the generated dataset's aggregate metrics (CTR, CPC) and the predefined industry profile targets.
