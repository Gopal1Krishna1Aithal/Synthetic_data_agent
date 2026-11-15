"""
server.py — HTTP REST Service for the Synthetic Data Agent (Agent 2).

PURPOSE:
Exposes HTTP endpoints so downstream agents (Budget Allocator, Performance Prediction,
Marketing Orchestrator) can query synthetic data via standard HTTP calls.

Uses Flask (pre-installed in environment) with support for FastAPI if available.

START SERVER:
    python server.py                # Runs on port 8000 by default

ENDPOINTS:
    GET  /health                    # Health check
    GET  /industries                # Supported verticals and benchmarks
    POST /generate                  # Generate synthetic dataset for a single industry
    POST /generate/batch            # Generate synthetic datasets for multiple industries

EXAMPLE CURL:
    curl -X POST http://localhost:8000/generate \
      -H "Content-Type: application/json" \
      -d '{"industry": "rcg", "dataset_type": "campaign_logs", "volume": 100}'
"""

import sys
import os
import json

from core import generate_synthetic_data, generate_batch, VALID_INDUSTRIES, _load_configs

try:
    from flask import Flask, request, jsonify, render_template
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ===============================================================
# 1. Flask App Implementation (Default)
# ===============================================================
def create_flask_app():
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def root():
        # If requested by a web browser, serve the interactive UI
        if "text/html" in request.headers.get("Accept", "") and request.args.get("format") != "json":
            try:
                return render_template("index.html")
            except Exception:
                pass
        return jsonify({
            "agent": "Agent 2 — Synthetic Data Creation Agent",
            "status": "running",
            "framework": "Flask",
            "supported_industries": sorted(VALID_INDUSTRIES),
            "supported_dataset_types": [
                "customer_profiles", "campaign_logs", "engagement_events", "all"
            ],
            "endpoints": {
                "GET  /":               "Interactive Web Dashboard (browser) or API overview (json)",
                "GET  /health":         "Health check",
                "GET  /industries":     "List supported industries and benchmarks",
                "POST /generate":       "Generate single industry dataset",
                "POST /generate/batch": "Generate multi-industry batch datasets",
            }
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "agent": "synthetic-data-agent"})

    @app.route("/industries", methods=["GET"])
    def list_industries():
        profiles, _ = _load_configs()
        info = {}
        for ind in sorted(VALID_INDUSTRIES):
            p = profiles.get(ind, {})
            info[ind] = {
                "ctr":                     p.get("ctr"),
                "cpc_inr":                 p.get("cpc"),
                "conversion_rate":         p.get("conversion_rate"),
                "avg_conversion_value_inr": p.get("avg_conversion_value"),
            }
        return jsonify(info)

    @app.route("/generate", methods=["POST"])
    def generate():
        payload = request.get_json(silent=True) or {}
        industry = payload.get("industry")
        if not industry:
            return jsonify({"status": "error", "error": "Missing required field 'industry'"}), 400

        try:
            vol = payload.get("volume") or payload.get("num_customers") or 100
            num_camps = payload.get("num_campaigns")
            if num_camps is not None:
                num_camps = int(num_camps)

            result = generate_synthetic_data(
                industry=industry,
                dataset_type=payload.get("dataset_type", "all"),
                volume=int(vol),
                seed_parameters=payload.get("seed_parameters"),
                num_campaigns=num_camps,
                max_events_per_campaign=int(payload.get("max_events_per_campaign", 200)),
                output_format="dict",
            )
            # Ensure status is set for web UI convenience
            response_payload = dict(result)
            response_payload["status"] = "success"
            return jsonify(response_payload)
        except ValueError as e:
            return jsonify({"status": "error", "error": str(e)}), 422
        except Exception as e:
            return jsonify({"status": "error", "error": f"Generation failed: {str(e)}"}), 500

    @app.route("/generate/batch", methods=["POST"])
    def batch():
        payload = request.get_json(silent=True) or {}
        industries = payload.get("industries")
        if not industries or not isinstance(industries, list):
            return jsonify({"error": "Missing or invalid 'industries' list"}), 400

        try:
            results = generate_batch(
                industries=industries,
                dataset_type=payload.get("dataset_type", "all"),
                volume_per_industry=int(payload.get("volume_per_industry", 100)),
                seed_parameters=payload.get("seed_parameters"),
                max_events_per_campaign=int(payload.get("max_events_per_campaign", 200)),
                output_format="dict",
            )
            return jsonify(results)
        except ValueError as e:
            return jsonify({"error": str(e)}), 422
        except Exception as e:
            return jsonify({"error": f"Batch generation failed: {str(e)}"}), 500

    return app


# Instantiate app for WSGI / tests
if HAS_FLASK:
    app = create_flask_app()
else:
    app = None


# ===============================================================
# Runner
# ===============================================================
if __name__ == "__main__":
    if HAS_FLASK:
        port = int(os.environ.get("PORT", 8000))
        print(f"Starting Synthetic Data Agent HTTP Server on http://0.0.0.0:{port} ...")
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        print("Error: Flask is not installed. Run: pip install flask")
        sys.exit(1)
