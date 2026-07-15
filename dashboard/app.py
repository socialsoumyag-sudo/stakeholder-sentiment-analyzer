"""
Streamlit Dashboard — Stakeholder Sentiment & Roadmap Risk Analyzer
---------------------------------------------------------------------
Visualizes:
  - Per-stakeholder risk-tag timeline across weeks
  - Stakeholder conflict map
  - Pre-emptive risk flags with source citations
  - Suggested roadmap adjustment

Run with:
    streamlit run dashboard/app.py

Expects data/pipeline_output.json to exist (run orchestrator.py first).
"""

import json
import os
import sys

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from ingestion.source_adapters import (
    from_manual, from_email_text, from_slack_export,
    from_chat_transcript, from_timestamped_transcript, to_pipeline_dicts,
)

st.set_page_config(page_title="Stakeholder Sentiment & Roadmap Risk", layout="wide")

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pipeline_output.json")
DEMO_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demo_output.json")

CATEGORY_COLORS = {
    "none": "#2e7d32",
    "hedging": "#f9a825",
    "deflection": "#ef6c00",
    "over_confidence": "#c62828",
    "escalation_avoidance": "#8e24aa",
    "conflicting_priorities": "#1565c0",
    "ERROR": "#616161",
}


def load_data():
    """Prefer a real, freshly-generated pipeline run. If none exists yet
    (e.g. a fresh clone, or a visitor on the hosted demo without their own
    API key), fall back to the static, hand-verified demo dataset so the
    dashboard is never empty."""
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            return json.load(f), False
    if os.path.exists(DEMO_DATA_PATH):
        with open(DEMO_DATA_PATH) as f:
            return json.load(f), True
    return None, False


def render_header():
    st.title("📊 Stakeholder Sentiment & Roadmap Risk Analyzer")
    st.caption(
        "Detects hedging, deflection, over-confidence, escalation-avoidance, and "
        "conflicting priorities across stakeholder status reports — then synthesizes "
        "a forward-looking roadmap risk view."
    )


def render_no_data_state():
    st.warning(
        "No pipeline output found yet. Run the pipeline first:\n\n"
        "```\nexport ANTHROPIC_API_KEY=sk-...\npython orchestrator.py\n```"
    )
    st.info(
        "This dashboard reads from `data/pipeline_output.json`, which is generated "
        "by running the classifier + synthesis agents over the synthetic status reports."
    )


def render_timeline(classified):
    st.subheader("Per-Stakeholder Risk Timeline")
    df = pd.DataFrame(classified)
    df = df[df["category"] != "ERROR"]

    stakeholders = sorted(df["stakeholder"].unique())
    for sh in stakeholders:
        sub = df[df["stakeholder"] == sh].sort_values("week")
        cols = st.columns([1] + [1] * len(sub))
        cols[0].markdown(f"**{sh}**  \n*{sub.iloc[0]['role']}*")
        for i, (_, row) in enumerate(sub.iterrows(), start=1):
            color = CATEGORY_COLORS.get(row["category"], "#999")
            with cols[i]:
                st.markdown(
                    f"<div style='background:{color}22;border-left:4px solid {color};"
                    f"padding:6px;border-radius:4px;font-size:0.8em'>"
                    f"<b>{row['week']}</b><br>{row['category']}<br>"
                    f"<i>conf: {row['confidence']:.2f}</i></div>",
                    unsafe_allow_html=True,
                )
                with st.expander("statement"):
                    st.write(row["text"])
                    st.caption(row["rationale"])


def render_conflict_map(conflicts):
    st.subheader("⚔️ Stakeholder Conflict Map")
    if not conflicts:
        st.info("No conflicts detected in this dataset.")
        return
    for c in conflicts:
        with st.container(border=True):
            st.markdown(f"**{' vs '.join(c['stakeholders'])}**")
            st.write(c["issue"])
            for ev in c.get("evidence", []):
                st.caption(f'"{ev}"')


def render_risk_flags(flags):
    st.subheader("🚩 Pre-emptive Risk Flags")
    if not flags:
        st.info("No risk flags raised.")
        return
    for f in sorted(flags, key=lambda x: -x.get("confidence", 0)):
        conf = f.get("confidence", 0)
        bar_color = "#c62828" if conf > 0.7 else "#f9a825" if conf > 0.4 else "#2e7d32"
        with st.container(border=True):
            st.markdown(f"**{f['risk']}**  \n"
                        f"<span style='color:{bar_color}'>Confidence: {conf:.0%}</span>",
                        unsafe_allow_html=True)
            st.write(f"→ {f['recommended_action']}")
            with st.expander("source statements"):
                for s in f.get("source_statements", []):
                    st.caption(f'"{s}"')


def render_roadmap(adjustment):
    st.subheader("🗺️ Suggested Roadmap Adjustment")
    st.markdown(adjustment)


def render_quarantine(quarantined):
    if not quarantined:
        return
    st.warning(f"⚠️ {len(quarantined)} statement(s) were quarantined by guardrails and "
               f"NOT sent to the classifier. Review before deciding whether to include them.")
    for q in quarantined:
        with st.container(border=True):
            st.markdown(f"**{q.get('stakeholder', 'Unknown')}** — *{q.get('topic', '')}*")
            st.code(q.get("text", ""), language=None)
            for flag in q.get("guardrail_flags", []):
                st.caption(f"🚩 {flag}")


def render_ingestion_ui():
    """Lets the user paste data from any supported source and run the
    pipeline directly from the dashboard, instead of editing Python files.
    """
    st.subheader("📥 Add Data From Any Source")
    st.caption(
        "Paste content from email, Slack, meeting transcripts, or plain chat logs. "
        "All PII is redacted and names pseudonymized locally before anything is sent "
        "to the model -- see the Privacy & Guardrails tab for details."
    )

    week = st.text_input("Week / batch label", value="Week 1")
    topic = st.text_input("Topic", value="General Status")

    source_type = st.selectbox(
        "Source type",
        ["Manual entry", "Email (raw text/.eml)", "Slack export (JSON)",
         "Chat transcript (Name: message)", "Meeting transcript (timestamped)"],
    )

    parsed_statements = None
    error_message = None

    if source_type == "Manual entry":
        col1, col2 = st.columns(2)
        stakeholder = col1.text_input("Stakeholder name")
        role = col2.text_input("Role")
        text = st.text_area("Statement text", height=100)
        if st.button("Add statement", key="manual_add"):
            if stakeholder and text:
                parsed_statements = [from_manual(stakeholder, role, week, topic, text)]
            else:
                error_message = "Stakeholder name and statement text are required."

    elif source_type == "Email (raw text/.eml)":
        raw = st.text_area("Paste raw email (including From:/Subject:/Date: headers)", height=200)
        if st.button("Parse email", key="email_add"):
            try:
                parsed_statements = [from_email_text(raw, week, topic)]
            except Exception as e:
                error_message = str(e)

    elif source_type == "Slack export (JSON)":
        raw = st.text_area("Paste Slack channel export JSON", height=200)
        if st.button("Parse Slack export", key="slack_add"):
            try:
                parsed_statements = from_slack_export(raw, week, topic)
            except Exception as e:
                error_message = str(e)

    elif source_type == "Chat transcript (Name: message)":
        raw = st.text_area("Paste transcript, one 'Name: message' per line", height=200)
        if st.button("Parse transcript", key="chat_add"):
            try:
                parsed_statements = from_chat_transcript(raw, week, topic)
            except Exception as e:
                error_message = str(e)

    elif source_type == "Meeting transcript (timestamped)":
        raw = st.text_area("Paste timestamped transcript, e.g. '[00:12:34] Name: text'", height=200)
        if st.button("Parse meeting transcript", key="meeting_add"):
            try:
                parsed_statements = from_timestamped_transcript(raw, week, topic)
            except Exception as e:
                error_message = str(e)

    if error_message:
        st.error(f"Could not parse input: {error_message}")

    if parsed_statements:
        st.success(f"Parsed {len(parsed_statements)} statement(s):")
        for s in parsed_statements:
            st.json({"stakeholder": s.stakeholder, "role": s.role, "text": s.text, "source": s.source})

        pending = st.session_state.setdefault("pending_statements", [])
        pending.extend(to_pipeline_dicts(parsed_statements))
        st.info(f"{len(pending)} statement(s) queued. Add more from other sources, "
                f"or run the pipeline below.")

    pending = st.session_state.get("pending_statements", [])
    if pending:
        st.divider()
        st.write(f"**{len(pending)} statement(s) queued for analysis**")
        col1, col2 = st.columns(2)
        if col1.button("🚀 Run pipeline on queued statements", type="primary"):
            if not os.environ.get("ANTHROPIC_API_KEY"):
                st.error("ANTHROPIC_API_KEY not set. Add it to your .env file first.")
            else:
                with st.spinner("Running guardrails, privacy scrubbing, classification, and synthesis..."):
                    from orchestrator_v2 import run_pipeline_v2
                    run_pipeline_v2(pending, verbose=False)
                st.session_state["pending_statements"] = []
                st.success("Pipeline complete. Switch to the Dashboard tab to see results.")
                st.rerun()
        if col2.button("Clear queue"):
            st.session_state["pending_statements"] = []
            st.rerun()


def render_privacy_info():
    st.subheader("🔒 Privacy & Guardrails")
    st.markdown("""
**What never leaves your machine:**
- Real stakeholder names -- replaced with `Stakeholder_A`, `Stakeholder_B`, etc. before any LLM call
- Emails, phone numbers, and employee IDs found inside statement text -- redacted before sending
- The real-name mapping is stored locally in `privacy/identity_mapping.json` (gitignored, never committed)

**Guardrails against manipulated input:**
- Every statement is checked for prompt-injection patterns (e.g. "ignore previous instructions") *before* it reaches the model
- Flagged statements are quarantined, not silently dropped or silently processed -- they need human review
- The classifier's own system prompt treats all input as data, never as instructions, as a second independent layer of defense

**What this does NOT yet do (be aware before relying on it for sensitive data):**
- No encryption at rest for the identity mapping file
- No role-based access control -- anyone with file access can see the audit log and mapping
- No live OAuth connections to Slack/Gmail/Teams -- all ingestion is manual paste for now
- Guardrail patterns are regex-based and will miss sophisticated injection attempts; treat this as one layer, not a complete defense
""")


def main():
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📥 Add Data", "🔒 Privacy & Guardrails"])

    with tab2:
        render_ingestion_ui()

    with tab3:
        render_privacy_info()

    with tab1:
        render_header()
        data, is_demo = load_data()
        if not data:
            render_no_data_state()
            return

        if is_demo:
            st.info(
                "📋 Showing static **demo data** (derived from the labeled synthetic reports "
                "in `data/synthetic_reports.py`) so you can see real, representative output "
                "without an API key. Head to the **Add Data** tab to run the live pipeline "
                "on your own input with your own `ANTHROPIC_API_KEY`.",
                icon="ℹ️",
            )

        classified = data.get("classified_statements", [])
        synthesis = data.get("synthesis", {})
        quarantined = data.get("quarantined_statements", [])

        render_quarantine(quarantined)
        render_timeline(classified)
        st.divider()

        if synthesis.get("error"):
            st.error(f"Synthesis step failed: {synthesis['error']}")
            return

        col1, col2 = st.columns(2)
        with col1:
            render_conflict_map(synthesis.get("conflict_map", []))
        with col2:
            render_risk_flags(synthesis.get("risk_flags", []))

        st.divider()
        render_roadmap(synthesis.get("roadmap_adjustment", "_No adjustment generated._"))


if __name__ == "__main__":
    main()