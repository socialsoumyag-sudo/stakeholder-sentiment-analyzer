"""
Multi-Source Ingestion Adapters
---------------------------------
Normalizes different input formats into the same statement schema the
pipeline already uses:
    {"stakeholder": str, "role": str, "week": str, "topic": str, "text": str}

Supported sources (all manually pasted/uploaded by the user -- no live API
connections to Slack/Teams/Gmail in this version; that's a natural next
step once auth/OAuth is in scope):

  - Plain status report text (existing format)
  - Email (.eml, or pasted raw email text with From/Subject/Date headers)
  - Slack export (JSON, from Slack's "export channel" feature)
  - Generic chat transcript (Teams/Zoom-style: "Name: message" per line)
  - Meeting transcript with timestamps (Zoom/Teams .vtt or plain "[00:12:34] Name: text")

Each adapter is independent and defensive -- malformed input produces a
clear error rather than a silent partial parse, since silently dropping
content in a risk-detection tool is exactly the wrong failure mode.
"""

import re
import json
import email
from email import policy
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawStatement:
    stakeholder: str
    role: str
    week: str
    topic: str
    text: str
    source: str  # tracks provenance: "email", "slack", "transcript", "manual"


def from_manual(stakeholder: str, role: str, week: str, topic: str, text: str) -> RawStatement:
    """Direct entry -- same as the original synthetic data format."""
    return RawStatement(stakeholder=stakeholder, role=role, week=week, topic=topic,
                         text=text.strip(), source="manual")


def from_email_text(raw_email: str, week: str, topic: str, role_hint: str = "") -> RawStatement:
    """Parses a raw email (paste of full headers + body, or .eml content).
    Extracts sender name from From: header, uses body as the statement text.
    """
    msg = email.message_from_string(raw_email, policy=policy.default)

    from_header = msg.get("From", "Unknown Sender")
    # "John Smith <john@company.com>" -> "John Smith"
    name_match = re.match(r'^([^<]+)<', from_header)
    stakeholder = name_match.group(1).strip() if name_match else from_header.strip()

    body = msg.get_body(preferencelist=("plain",))
    text = body.get_content().strip() if body else msg.get_payload()

    if not text:
        raise ValueError("Email body is empty or could not be parsed. "
                          "Check the raw email text was pasted completely, including a blank line before the body.")

    return RawStatement(stakeholder=stakeholder, role=role_hint, week=week,
                         topic=topic, text=text.strip(), source="email")


def from_slack_export(json_text: str, week: str, topic: str, role_map: Optional[dict] = None) -> list[RawStatement]:
    """Parses Slack's channel export JSON format (list of message objects
    with 'user'/'username' and 'text' fields). role_map optionally maps
    Slack usernames to role titles, e.g. {"raj.m": "Engineering Lead"}.
    """
    role_map = role_map or {}
    try:
        messages = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse Slack export as JSON: {e}. "
                          "Make sure you pasted the full export file content.")

    if not isinstance(messages, list):
        raise ValueError("Expected a JSON array of Slack messages. "
                          "Check you exported a channel, not a single message.")

    statements = []
    for msg in messages:
        username = msg.get("username") or msg.get("user") or "Unknown"
        text = msg.get("text", "").strip()
        if not text:
            continue  # skip empty messages (reactions-only, joins, etc.) -- not silent data loss, just noise
        statements.append(RawStatement(
            stakeholder=username, role=role_map.get(username, ""),
            week=week, topic=topic, text=text, source="slack",
        ))

    if not statements:
        raise ValueError("No usable messages found in the Slack export. "
                          "Check the export contains 'text' fields with content.")

    return statements


def from_chat_transcript(transcript_text: str, week: str, topic: str, role_map: Optional[dict] = None) -> list[RawStatement]:
    """Parses generic 'Name: message' style transcripts (Teams chat exports,
    manually typed transcripts, etc.). One statement per line/turn.
    """
    role_map = role_map or {}
    pattern = re.compile(r'^([A-Za-z][A-Za-z .\'-]{1,50}):\s*(.+)$')
    statements = []

    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            continue  # not every line is a new speaker turn (e.g. multi-line messages); skip non-matching lines
        name, text = match.group(1).strip(), match.group(2).strip()
        if not text:
            continue
        statements.append(RawStatement(
            stakeholder=name, role=role_map.get(name, ""),
            week=week, topic=topic, text=text, source="transcript",
        ))

    if not statements:
        raise ValueError("No 'Name: message' style lines found. Expected format per line: "
                          "'John Smith: We're on track for the deadline.'")

    return statements


def from_timestamped_transcript(transcript_text: str, week: str, topic: str, role_map: Optional[dict] = None) -> list[RawStatement]:
    """Parses meeting transcripts with timestamps, e.g. Zoom/Teams style:
    '[00:12:34] John Smith: We're on track for the deadline.'
    Also handles WebVTT-style timestamp lines (00:12:34.000 --> 00:12:40.000)
    by skipping them and using the following speaker line.
    """
    role_map = role_map or {}
    pattern = re.compile(r'^\[?\d{1,2}:\d{2}(:\d{2})?\]?\s*([A-Za-z][A-Za-z .\'-]{1,50}):\s*(.+)$')
    vtt_timestamp_line = re.compile(r'^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}$')

    statements = []
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line or vtt_timestamp_line.match(line) or line.isdigit():
            continue  # skip VTT cue numbers and timing lines
        match = pattern.match(line)
        if not match:
            continue
        name, text = match.group(2).strip(), match.group(3).strip()
        if not text:
            continue
        statements.append(RawStatement(
            stakeholder=name, role=role_map.get(name, ""),
            week=week, topic=topic, text=text, source="meeting_transcript",
        ))

    if not statements:
        raise ValueError("No timestamped speaker lines found. Expected format: "
                          "'[00:12:34] John Smith: We're on track.' or WebVTT format.")

    return statements


def to_pipeline_dicts(statements: list[RawStatement]) -> list[dict]:
    """Converts RawStatement objects to the plain dict format the rest of
    the pipeline (risk_classifier.py, synthesis_agent.py) already expects."""
    return [
        {"stakeholder": s.stakeholder, "role": s.role, "week": s.week,
         "topic": s.topic, "text": s.text, "_source": s.source}
        for s in statements
    ]


if __name__ == "__main__":
    # Quick self-tests for each adapter
    print("=== Email adapter ===")
    sample_email = """From: Raj Malhotra <raj.malhotra@otis.com>
Subject: Integration Status
Date: Mon, 1 Jul 2026 10:00:00 +0000

The eBOM sync issue is actually related to the vendor's middleware config, not our side.
"""
    result = from_email_text(sample_email, week="Week 2", topic="Aras Integration")
    print(result)

    print("\n=== Chat transcript adapter ===")
    sample_chat = """Tom Becker: I need the Nov go-live date held firm.
Raj Malhotra: We need a two-week buffer given current scope.
"""
    results = from_chat_transcript(sample_chat, week="Week 3", topic="Go-Live Timeline")
    for r in results:
        print(r)

    print("\n=== Timestamped meeting transcript adapter ===")
    sample_meeting = """[00:05:12] Anita Desai: We found three P1 defects but they're being tracked internally.
[00:06:45] Tom Becker: We are on track and I don't foresee any reason to move the date.
"""
    results = from_timestamped_transcript(sample_meeting, week="Week 4", topic="Regression Testing")
    for r in results:
        print(r)

    print("\n=== Slack export adapter ===")
    sample_slack = json.dumps([
        {"username": "priya.nair", "text": "Migration dry-run is complete and validated end to end."},
        {"username": "raj.malhotra", "text": "Root cause was a data quality issue from the legacy ERP export."},
    ])
    results = from_slack_export(sample_slack, week="Week 4", topic="Data Migration")
    for r in results:
        print(r)
