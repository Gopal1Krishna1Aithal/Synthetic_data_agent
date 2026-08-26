import random
from datetime import datetime, timedelta
from relationships import calculate_campaign_metrics

def generate_engagement_events(campaigns, customers, profiles, rules, max_events_per_campaign=10000):
    events = []
    event_counter = 1
    
    for campaign in campaigns:
        metrics = calculate_campaign_metrics(campaign, profiles, rules)
        
        # Determine how many events to write to raw logs
        raw_imps = metrics["impressions"]
        clicks = metrics["clicks"]
        conversions = metrics["conversions"]
        cost = metrics["cost"]
        revenue = metrics["revenue"]
        
        # Calculate event-level cost and revenue
        cpc = cost / clicks if clicks > 0 else 0
        rev_per_conv = revenue / conversions if conversions > 0 else 0
        
        # Number of impressions that did NOT result in a click or conversion
        pure_impressions = max(0, raw_imps - clicks - conversions)
        total_events_intended = pure_impressions + clicks + conversions
        
        if total_events_intended > max_events_per_campaign:
            ratio = max_events_per_campaign / total_events_intended
            sampled_pure_imps = int(pure_impressions * ratio)
            
            # Use stochastic (probabilistic) rounding for clicks and conversions.
            # When expected conversions is 0.55, standard round() always returns 1,
            # which permanently inflates the sampled rate. Stochastic rounding yields
            # 1 with 55% probability and 0 with 45% probability, ensuring the math
            # converges correctly across multiple campaigns.
            s_clicks_float = clicks * ratio
            sampled_clicks = int(s_clicks_float) + (1 if random.random() < (s_clicks_float - int(s_clicks_float)) else 0)
            
            s_conv_float = conversions * ratio
            sampled_conversions = int(s_conv_float) + (1 if random.random() < (s_conv_float - int(s_conv_float)) else 0)
        else:
            sampled_pure_imps = pure_impressions
            sampled_clicks = clicks
            sampled_conversions = conversions

        # -------------------------------------------------------
        # Attribution weight (linear model):
        # - impression: 0.0  (view-through, no click credit)
        # - conversion: 1.0  (the confirmed outcome)
        # - click:      1/n  (equal share across all clicks in campaign)
        # This is deterministic per campaign — auditable by downstream agents.
        # -------------------------------------------------------
        click_weight = round(1.0 / sampled_clicks, 6) if sampled_clicks > 0 else 0.0
            
        # Create a list of event types to generate
        event_types = (["impression"] * sampled_pure_imps) + (["click"] * sampled_clicks) + (["conversion"] * sampled_conversions)
        random.shuffle(event_types)
        
        # Distribute over campaign duration
        start_dt = datetime.strptime(campaign["start_date"], "%Y-%m-%d")
        end_dt = datetime.strptime(campaign["end_date"], "%Y-%m-%d")
        delta_seconds = int((end_dt - start_dt).total_seconds())
        
        # Carry industry from campaign for independent vertical filtering downstream
        campaign_industry = campaign["industry"]
        
        for etype in event_types:
            # Generate random timestamp within campaign
            random_offset = random.randint(0, delta_seconds)
            evt_timestamp = start_dt + timedelta(seconds=random_offset)
            
            # Select random customer
            cust = random.choice(customers)

            # Attribution weight by event type
            if etype == "impression":
                attr_weight = 0.0
            elif etype == "conversion":
                attr_weight = 1.0
            else:  # click
                attr_weight = click_weight
            
            # Form event dict
            evt = {
                "event_id": f"EVT-{event_counter:08d}",
                "timestamp": evt_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "customer_id": cust["customer_id"],
                "campaign_id": campaign["campaign_id"],
                "event_type": etype,
                "industry": campaign_industry,
                "attribution_weight": attr_weight,
                "cost": round(cpc, 4) if etype == "click" else 0.0,
                "revenue": round(rev_per_conv, 4) if etype == "conversion" else 0.0
            }
            events.append(evt)
            event_counter += 1
            
    return events
