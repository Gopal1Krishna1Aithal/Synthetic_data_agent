# Synthetic Data Creation Agent

A highly advanced, mathematically rigorous synthetic data generation pipeline designed to simulate complex, multi-vertical digital marketing datasets. This project is purpose-built to act as the foundational training data for downstream Machine Learning models (such as Predictive Churn, Budget Allocators, and Campaign Performance predictors) in a privacy-safe, PII-free environment.

## Overview
Unlike typical synthetic data generators that output "random noise," this engine implements a **strict marketing physics engine**. Every click, impression, and conversion is bound by economic constraints (budget ceilings, audience saturation limits, industry-specific auction costs). 

If a model trains on this data, it will learn real-world marketing truths (e.g., *LinkedIn B2B campaigns drive high CPMs but generate valuable Enterprise leads, while Meta drives cheap Top-of-Funnel reach*).

---

## How Close Is This To Real-World Data?
**Extremely close.** We engineered this pipeline to replicate the anomalies and friction of the real-world Ad-Tech ecosystem:

### 1. iOS 14 Anonymous User Simulation (ATT)
In the real world, tracking is never 100% perfect. Post-iOS 14, a massive portion of top-of-funnel traffic is anonymous.
* **Our Logic:** The pipeline randomly forces 30% of all `impression` and `click` events to have `customer_id: null`. This ensures downstream ML models don't overfit on the fantasy of perfect attribution, and learn to handle anonymous, untracked traffic natively.

### 2. Trailing Attribution Windows
Real users don't always buy a product the exact second they click an ad. 
* **Our Logic:** We decoupled clicks from conversions. When a user converts, the engine applies a randomized `attribution_delay` of 0 to 7 days. This allows conversions to realistically "trail" the click, sometimes occurring even after the campaign's formal `end_date`.

### 3. Campaign Lifecycle Curves (Beta Distributions)
Uniformly random engagement timestamps teach ML models that "time doesn't matter."
* **Our Logic:** Engagement events are generated using a right-skewed Beta Distribution (`alpha=1.5, beta=3.5`). This mathematically simulates a massive spike of user engagement on launch day that slowly tapers off over the course of the campaign.

### 4. Audience Saturation & Budget Physics
A campaign with a ₹10,000,000 budget but only 5,000 target users cannot physically spend its money without hitting extreme frequency caps.
* **Our Logic:** We enforce a `max_frequency` cap (e.g., 15 views per user). If the budget pushes impressions past this cap, the audience is marked "saturated". Impressions halt, and the campaign fails to spend its full budget. Downstream performance models will learn the limits of scale.

### 5. Perfect LTV Referential Integrity
In many synthetic pipelines, a user's Lifetime Value (LTV) is guessed, contradicting their actual event history.
* **Our Logic:** We completely solved the "LTV Paradox." Customer profiles are generated with ₹0 spend. The pipeline then dynamically aggregates the `revenue` from every generated `conversion` event back into the user's profile. If a profile says a user's LTV is ₹50,000, there are exactly ₹50,000 worth of conversions in the event log. 

### 6. "Dirty Data" Injection
* **Our Logic:** 2% of `age` and `gender` values are explicitly dropped (`null`). This forces downstream predictive models (like Churn) to learn how to impute missing features gracefully, preventing production crashes.

---

## How Close Is This To Production-Level Code?
This repository is built to strict Software Engineering and ML Engineering standards:
* **JSON Schema Enforced:** Every dataset (`customer_profiles`, `campaign_logs`, `engagement_events`) is strictly validated against a JSON Schema before export. It will immediately throw an error if the schema breaks.
* **Statistically Normalized:** We use per-industry normalization factors to guarantee that regardless of how much variance exists at the campaign level, the *aggregate* metrics for a vertical (e.g., BFSI) perfectly converge to the defined benchmarks in `industry_profiles.json` (Unbiased at large `n`).
* **Memory Efficient:** It supports chunking via `--max-events-per-campaign` to prevent Memory/OOM blowups on consumer hardware.
* **API Ready:** The `api.py` exposes a robust CLI that allows downstream teams to fetch only the columns they need via presets (`--preset churn`, `--preset campaign-performance`).

---

## Quickstart

The CLI is highly dynamic. 

### 1. Run a small test (validates schema, no files written)
```bash
python api.py --dry-run
```

### 2. Generate actual data (All 6 verticals)
```bash
python api.py --num-customers 600 --num-campaigns 300
```

### 3. Generate focused CSV data for a specific Agent
If the Predictive Churn intern only needs RFM (Recency, Frequency, Monetary) columns for the Travel and Healthcare verticals:
```bash
python api.py --industries travel healthcare --preset churn --output-format csv
```

### 4. View the Generation Report
Every successful run outputs a `generation_report.json` detailing the CLI parameters used, the volumes generated, and a full statistical deviation report to prove mathematical soundness.
