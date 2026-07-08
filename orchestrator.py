"""
Orchestrator
------------
Runs the full pipeline end-to-end:
  synthetic reports -> risk classifier (per-statement) -> synthesis agent (cross-statement)
  -> combined output written to data/pipeline_output.json

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python orchestrator.py
"""

import json
import os
import sys
from dataclasses import asdict

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from data.synthetic_reports import to_dicts
from agents.risk_classifier import classify_all
from agents.synthesis_agent import synthesize


def run_pipeline(verbose: bool = True) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key, "
            "or export it directly: export ANTHROPIC_API_KEY=sk-..."
        )

    statements = to_dicts()
    if verbose:
        print(f"Loaded {len(statements)} synthetic statements.")

    classified = classify_all(statements)
    classified_dicts = [asdict(c) for c in classified]
    errors = [c for c in classified_dicts if c["error"]]
    if verbose:
        print(f"Classified {len(classified)} statements ({len(errors)} errors).")

    synthesis = synthesize(classified_dicts)
    synthesis_dict = asdict(synthesis)
    if verbose:
        if synthesis.error:
            print(f"⚠️  Synthesis error: {synthesis.error}")
        else:
            print(f"Synthesis complete: {len(synthesis.conflict_map)} conflicts, "
                  f"{len(synthesis.risk_flags)} risk flags.")

    output = {
        "classified_statements": classified_dicts,
        "synthesis": synthesis_dict,
    }

    out_path = os.path.join(os.path.dirname(__file__), "data", "pipeline_output.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    if verbose:
        print(f"Full pipeline output saved to {out_path}")

    return output


if __name__ == "__main__":
    run_pipeline()
