# Stakeholder Sentiment & Roadmap Risk Analyzer

**Detects hedging, deflection, over-confidence, and escalation-avoidance in enterprise status reports — then synthesizes a forward-looking roadmap risk view across stakeholders.**

Most sentiment tools tell you a report *sounds* positive. This tells you whether it's *hiding something* — and if so, what that means for your timeline.

---

## The problem

In large programmes, status reports are where risk goes to hide. "Should be fine," "mostly on track," "we're handling it internally" — these phrases pass every generic sentiment check as neutral-to-positive, while actually signaling exactly the risk patterns that blow up two months later as executive escalations.

This project came out of running the Transformation Office for a $200M+ enterprise programme, where reading between the lines of stakeholder updates was a full-time skill. This tries to make that skill machine-assisted.

## What it does

1. **Extracts and tags** each stakeholder statement from a status report into one of six categories: `hedging`, `deflection`, `over_confidence`, `escalation_avoidance`, `conflicting_priorities`, or `none` (clean/appropriately confident) — with a confidence score and the exact trigger phrase, not a black-box label.
2. **Synthesizes across stakeholders and weeks** to produce:
   - A **conflict map** — where two stakeholders' stated positions actually contradict each other
   - **Pre-emptive risk flags** — specific, source-cited risks worth escalating now, before they surface on their own
   - A **suggested roadmap adjustment** — a concrete recommendation, not just a red/amber/green status
3. **Visualizes it** in a dashboard: a per-stakeholder risk timeline, the conflict map, and the roadmap recommendation.

A pre-generated example is included at `data/sample_output.json` so you can see real output without needing an API key first.

## Architecture

```
synthetic status reports
        │
        ▼
  risk classifier agent   ── tags each statement, cites trigger phrase
        │
        ▼
  synthesis agent         ── reasons across all tagged statements
        │
        ▼
  Streamlit dashboard      ── timeline + conflict map + roadmap view
```

Two agents, single-responsibility, orchestrated sequentially (`orchestrator.py`). This mirrors the Orchestrator + specialist-agent pattern from the earlier [multi-agent PMO system](#) this project builds on — separating "tag the sentiment" from "reason about what the sentiment means" keeps each piece independently testable and swappable.

## Quickstart

```bash
git clone <this-repo>
cd stakeholder-sentiment
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY

# Run the full pipeline
python orchestrator.py

# View the dashboard
streamlit run dashboard/app.py

# Run tests (no API key needed)
python tests/test_core.py

# Run the eval harness (measures classifier accuracy against ground truth)
python evals/eval_classifier.py
```

## Why this is more than a prompt wrapper

- **Grounded, not vibes-based**: every classification cites the exact phrase that triggered it. Every risk flag cites the source statement. Nothing is asserted without a traceable source.
- **Measured, not assumed**: `evals/eval_classifier.py` scores the classifier against hand-labeled ground truth (baked into the synthetic data) and reports precision/recall per category — not just "it looked right when I tried it."
- **Tested where testing is meaningful**: `tests/test_core.py` covers the deterministic logic (data integrity, payload construction, JSON validation) without asserting on non-deterministic LLM output, which would be a brittle, false signal.
- **Fails loudly, not silently**: API calls have retry logic with exponential backoff, and malformed/failed responses are surfaced as explicit errors — never silently treated as "no risk detected."

## Scope — what this does *not* do (yet)

- Runs on synthetic data only. It has not been validated on real enterprise status reports (by design — no confidentiality risk, but also no claim of real-world calibration yet).
- The risk taxonomy (6 categories) is a starting point, not an exhaustive model of executive-communication risk.
- No fine-tuned classifier yet — this uses few-shot prompting with Claude. A natural v2 would fine-tune a small open model on a larger labeled set for lower latency/cost at scale.
- No authentication, multi-user support, or persistence layer — this is a working prototype, not a production PMO tool.

## Tech stack

Python · Anthropic API (Claude) · Streamlit · pandas · pytest

## Background

Built by [Soumya Ghatak](https://linkedin.com/in/soumyaghatakiimb) — Senior Program/Transformation Manager, IIM Bangalore MBA, PMP®. This extends an earlier multi-agent programme-management system (Orchestrator + Planner/Scheduler/Memory/Calendar-Sync agents) built during a $200M+ digital transformation programme at Otis Elevator.
