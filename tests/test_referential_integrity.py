import os
import json
import pytest
from generators.customer_profiles_gen import generate_customer_profiles
from generators.campaign_logs_gen import generate_campaign_logs
from generators.engagement_events_gen import generate_engagement_events

def test_referential_integrity():
    # Load configs
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profiles_path = os.path.join(base_dir, "config", "industry_profiles.json")
    rules_path = os.path.join(base_dir, "config", "relationship_rules.json")
    
    with open(profiles_path, 'r') as f:
        profiles = json.load(f)
    with open(rules_path, 'r') as f:
        rules = json.load(f)
        
    # Generate mock datasets
    customers = generate_customer_profiles(30)
    campaigns = generate_campaign_logs(5, list(profiles.keys()))
    events = generate_engagement_events(campaigns, customers, profiles, rules)
    
    # Extract IDs
    customer_ids = {c["customer_id"] for c in customers}
    campaign_ids = {c["campaign_id"] for c in campaigns}
    
    # Assert integrity
    for event in events:
        assert event["customer_id"] in customer_ids, f"Orphaned customer_id: {event['customer_id']}"
        assert event["campaign_id"] in campaign_ids, f"Orphaned campaign_id: {event['campaign_id']}"
        
    print(f"Verified referential integrity for {len(events)} events.")
