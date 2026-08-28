import random
from datetime import datetime, timedelta
from relationships import calculate_campaign_metrics


def generate_engagement_events(campaigns, customers, profiles, rules, max_events_per_campaign=10_000):
    """
    Generate engagement events for each campaign.

    Event model (mutually exclusive per interaction):
      - impression  : ad shown, user did NOT click
      - click       : user clicked but did NOT convert
      - conversion  : user clicked AND converted (one event — not click + conversion)

    This means:
      CTR  = (click_events + conversion_events) / total_impressions_served
      CR   = conversion_events / (click_events + conversion_events)

    Customers are scoped to their matching industry to prevent cross-vertical
    join corruption downstream (e.g. a Manufacturing campaign should never
    be attributed to a BFSI customer).
    """
    events = []
    event_counter = 1

    # ---------------------------------------------------------------
    # Group customers by industry ONCE before the loop.
    # Prevents O(n) linear scans and guarantees industry isolation.
    # ---------------------------------------------------------------
    customers_by_industry = {}
    for c in customers:
        customers_by_industry.setdefault(c["industry"], []).append(c)

    for campaign in campaigns:
        metrics           = calculate_campaign_metrics(campaign, profiles, rules)
        
        # Stamp historical metrics directly onto the campaign log
        # so downstream models can train on it directly (like real Ad Platform APIs)
        campaign.update({
            "reach":        metrics["reach"],
            "impressions":  metrics["impressions"],
            "clicks":       metrics["total_clicks"],
            "conversions":  metrics["conversions"],
            "leads":        metrics["leads"],
            "spend":        metrics["spend"],
            "cpm":          metrics["cpm"],
            "cpl":          metrics["cpl"]
        })

        raw_imps          = metrics["impressions"]
        non_conv_clicks   = metrics["non_conv_clicks"]   # clicked but didn't convert
        conversions       = metrics["conversions"]        # clicked AND converted
        total_clicks      = metrics["total_clicks"]       # non_conv_clicks + conversions
        cost              = metrics["cost"]
        avg_value         = metrics["avg_conversion_value"]

        # Per-click cost (uniform within campaign — variance is at campaign level via noise)
        cpc = cost / total_clicks if total_clicks > 0 else 0.0

        # pure_impressions = ad shown but not clicked at all
        # total reach = pure_imps + non_conv_clicks + conversions = raw_imps ✓
        pure_impressions      = max(0, raw_imps - total_clicks)
        total_events_intended = pure_impressions + non_conv_clicks + conversions

        # ---------------------------------------------------------------
        # Proportional sampling (cap at max_events_per_campaign).
        # Stochastic rounding: avoids ceiling bias for rare-event verticals
        # (e.g. Manufacturing CR=1%). A fractional expectation of 0.55
        # resolves to 1 with 55% probability and 0 with 45% — unbiased.
        # ---------------------------------------------------------------
        if total_events_intended > max_events_per_campaign:
            ratio = max_events_per_campaign / total_events_intended

            def stochastic_round(x):
                floor = int(x)
                return floor + (1 if random.random() < (x - floor) else 0)

            sampled_pure_imps     = stochastic_round(pure_impressions * ratio)
            sampled_non_conv      = stochastic_round(non_conv_clicks  * ratio)
            sampled_conversions   = stochastic_round(conversions      * ratio)
        else:
            sampled_pure_imps   = pure_impressions
            sampled_non_conv    = non_conv_clicks
            sampled_conversions = conversions

        # ---------------------------------------------------------------
        # Attribution weight (linear model):
        #   impression : 0.0  — view-through, no click credit
        #   click      : 1/n  — equal share across all sampled click events
        #   conversion : 1.0  — confirmed outcome gets full credit
        #
        # "All click events" = non_conv + conversions (both consumed a click action).
        # ---------------------------------------------------------------
        total_sampled_clicks = sampled_non_conv + sampled_conversions
        click_weight = round(1.0 / total_sampled_clicks, 6) if total_sampled_clicks > 0 else 0.0

        # ---------------------------------------------------------------
        # Industry-scoped customer pool — no cross-vertical contamination.
        # Falls back to all customers only if the industry pool is empty
        # (defensive guard against mis-configured generators).
        # ---------------------------------------------------------------
        campaign_industry  = campaign["industry"]
        industry_customers = customers_by_industry.get(campaign_industry) or list(customers)

        # Build and shuffle the event list
        event_types = (
            ["impression"] * sampled_pure_imps
            + ["click"]      * sampled_non_conv
            + ["conversion"] * sampled_conversions
        )
        random.shuffle(event_types)

        # Timestamps Beta-distributed across campaign window (right-skewed)
        # Represents launch-day spike tapering off (alpha=1.5, beta=3.0)
        start_dt      = datetime.strptime(campaign["start_date"], "%Y-%m-%d")
        end_dt        = datetime.strptime(campaign["end_date"],   "%Y-%m-%d")
        delta_seconds = max(1, int((end_dt - start_dt).total_seconds()))

        for etype in event_types:
            # random.betavariate(1.5, 3.5) yields values concentrated towards the lower end (0.0 - 0.4)
            fraction      = random.betavariate(1.5, 3.5)
            evt_timestamp = start_dt + timedelta(seconds=int(fraction * delta_seconds))
            cust          = random.choice(industry_customers)

            if etype == "impression":
                attr_weight = 0.0
                evt_cost    = 0.0
                evt_revenue = 0.0
            elif etype == "click":
                attr_weight = click_weight
                evt_cost    = round(cpc, 4)
                evt_revenue = 0.0
            else:  # conversion — click + convert in one event
                attr_weight = 1.0
                evt_cost    = round(cpc, 4)  # conversion also consumed a click cost
                # Revenue drawn INDEPENDENTLY per event — realistic per-event variance
                # for Revenue Prediction model (not a uniform split of a pre-summed total)
                evt_revenue = round(random.uniform(avg_value * 0.70, avg_value * 1.30), 2)

            events.append({
                "event_id":           f"EVT-{event_counter:08d}",
                "timestamp":          evt_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "customer_id":        cust["customer_id"],
                "campaign_id":        campaign["campaign_id"],
                "event_type":         etype,
                "industry":           campaign_industry,
                "attribution_weight": attr_weight,
                "cost":               evt_cost,
                "revenue":            evt_revenue,
            })
            event_counter += 1

    return events
