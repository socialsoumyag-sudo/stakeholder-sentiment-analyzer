"""
Roadmap Synthesis Agent
------------------------
Takes the classified, risk-tagged statements across all stakeholders/weeks
and produces:
  1. A stakeholder-conflict map (who wants what, where it clashes)
  2. Pre-emptive risk flags (with confidence + source citation)
  3. A suggested roadmap adjustment

This agent does NOT re-classify sentiment — it consumes the output of
risk_classifier.py and reasons over it. Kept as a separate agent so each
piece is independently testable (single-responsibility, matches the
Orchestrator + specialist-agent pattern used in the original multi-agent
PMO system).
"""

import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Optional

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a programme-risk synthesis agent. You receive a list of \
stakeholder statements from a status report, each already tagged with a risk \
category (hedging, deflection, over_confidence, escalation_avoidance, \
conflicting_priorities, or none) by an upstream classifier.

Your job is to reason ACROSS statements (not re-classify individual ones) and produce:

1. "conflict_map": a list of conflicts between stakeholders, each with:
   - "stakeholders": [names involved]
   - "issue": short description of what they disagree on
   - "evidence": list of exact quotes (verbatim from the input) that show the conflict

2. "risk_flags": a list of pre-emptive risks to escalate, each with:
   - "risk": short description
   - "confidence": float 0.0-1.0
   - "source_statements": list of exact quotes supporting this flag
   - "recommended_action": one sentence

3. "roadmap_adjustment": a short paragraph (3-5 sentences) recommending how the
   roadmap/timeline should be adjusted given the accumulated risk signals,
   referencing specific stakeholders and weeks.

Respond with ONLY a JSON object matching this structure, no markdown fences, no preamble.
Do not invent facts not supported by the input statements."""


@dataclass
class SynthesisResult:
    conflict_map: list
    risk_flags: list
    roadmap_adjustment: str
    error: Optional[str] = None


def _build_input_payload(classified: list[dict]) -> str:
    """Formats classified statements into a compact input for the synthesis agent."""
    lines = []
    for c in classified:
        if c.get("category") == "ERROR":
            continue  # skip statements the classifier failed on
        lines.append(
            f"- [{c['week']}] {c['stakeholder']} ({c['role']}) on {c['topic']}: "
            f'"{c["text"]}" '
            f"[tagged: {c['category']}, confidence: {c['confidence']}]"
        )
    return "\n".join(lines)


def _call_with_retry(client: anthropic.Anthropic, payload: str, max_retries: int = 3) -> dict:
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=3000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": payload}],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)

            for key in ("conflict_map", "risk_flags", "roadmap_adjustment"):
                if key not in parsed:
                    raise ValueError(f"Missing key in synthesis output: {key}")

            return parsed
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            last_error = str(e)
            time.sleep(0.5 * (attempt + 1))
        except anthropic.APIError as e:
            last_error = f"API error: {e}"
            time.sleep(1.0 * (attempt + 1))

    return {"error": last_error or "Unknown failure after retries"}


def synthesize(classified: list[dict]) -> SynthesisResult:
    if not classified:
        return SynthesisResult(conflict_map=[], risk_flags=[], roadmap_adjustment="",
                                error="No classified statements provided")

    client = anthropic.Anthropic()
    payload = _build_input_payload(classified)
    result = _call_with_retry(client, payload)

    if "error" in result:
        return SynthesisResult(conflict_map=[], risk_flags=[], roadmap_adjustment="",
                                error=result["error"])

    return SynthesisResult(
        conflict_map=result["conflict_map"],
        risk_flags=result["risk_flags"],
        roadmap_adjustment=result["roadmap_adjustment"],
        error=None,
    )


if __name__ == "__main__":
    classified_path = os.path.join(os.path.dirname(__file__), "..", "data", "classified_results.json")
    with open(classified_path) as f:
        classified = json.load(f)

    result = synthesize(classified)

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthesis_result.json")
    with open(out_path, "w") as f:
        json.dump(asdict(result), f, indent=2)

    if result.error:
        print(f"❌ Synthesis failed: {result.error}")
    else:
        print(f"✅ Synthesis complete. {len(result.conflict_map)} conflicts, "
              f"{len(result.risk_flags)} risk flags. Saved to {out_path}")
