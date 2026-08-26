# Synthetic Data Agent

A pipeline tool designed to generate realistic marketing datasets, containing customer demographic profiles, advertising campaign metadata, and simulated engagement clickstream events (impressions, clicks, and conversions).

## Directory Structure

```
synthetic-data-agent/
├── README.md                          <-- Setup instructions
├── api.py                             <-- Main run file: generate(industry, type)
├── relationships.py                   <-- The engine that links budgets to clicks
├── validation.py                      <-- Stat checker to ensure data looks real
│
├── config/                            <-- Tweakable settings (no code here)
│   ├── industry_profiles.json         <-- Holds CPC/CTR numbers and seasonality
│   └── relationship_rules.json        <-- Holds the correlation math 
│
├── generators/                        <-- The actual fake-data creators
│   ├── campaign_logs_gen.py
│   ├── customer_profiles_gen.py
│   └── engagement_events_gen.py
│
├── schemas/                           <-- The strict JSON contracts
│   ├── campaign_logs.schema.json
│   ├── customer_profiles.schema.json
│   └── engagement_events.schema.json
│
├── tests/                             <-- Automated safety checks
│   └── test_referential_integrity.py  <-- Ensures no orphan IDs across files
│
└── outputs/                           <-- Where the generated CSVs/JSONs land
```

## Setup & Running

### Requirements
- Python 3.8+
- Optional: `jsonschema` (for full JSON Schema contract validation)
- Optional: `pytest` (to run the automated test suite)

To install dependencies:
```bash
pip install jsonschema pytest
```

### Running the Generator
To generate mock data using default parameters:
```bash
python api.py
```

To customize parameters:
```bash
python api.py --num-customers 250 --num-campaigns 20 --output-format csv --output-dir custom_outputs
```

## Running Tests
Run pytest in the main project folder to ensure referential integrity checks pass successfully:
```bash
pytest tests/
```
