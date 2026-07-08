"""
Synthetic Status Report Generator
----------------------------------
Generates realistic enterprise programme status reports across multiple
stakeholders and time points, with deliberately engineered risk-language
patterns for demo/eval purposes:

  - hedging              ("should be fine", "mostly on track")
  - deflection           (blame shifted to another team/vendor)
  - over_confidence      (unrealistic certainty despite known blockers)
  - escalation_avoidance (known issue not raised to leadership)
  - conflicting_priorities (stakeholder wants X, another wants not-X)

Each statement is labeled with its intended ground-truth risk tag so this
same file doubles as the eval set for the classifier (see evals/).
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os

@dataclass
class Statement:
    stakeholder: str
    role: str
    week: str
    topic: str
    text: str
    ground_truth_tag: Optional[str] = None  # None = neutral/clean statement


REPORTS: list[Statement] = [
    # ---- Week 1 ----
    Statement("Raj Malhotra", "Engineering Lead", "Week 1", "Aras Integration",
        "Integration testing is progressing well, we expect to close out the sprint on schedule.",
        None),
    Statement("Priya Nair", "Vendor PM (Implementation Partner)", "Week 1", "Data Migration",
        "Data migration should be fine, we've handled similar cutovers before.",
        "hedging"),
    Statement("Tom Becker", "Business Sponsor", "Week 1", "Go-Live Timeline",
        "I need the Nov go-live date held firm regardless of what engineering says about scope.",
        "conflicting_priorities"),
    Statement("Anita Desai", "QA Lead", "Week 1", "Test Coverage",
        "Test coverage is mostly on track, a few edge cases still pending review.",
        "hedging"),

    # ---- Week 2 ----
    Statement("Raj Malhotra", "Engineering Lead", "Week 2", "Aras Integration",
        "The eBOM sync issue is actually related to the vendor's middleware config, not our side.",
        "deflection"),
    Statement("Priya Nair", "Vendor PM (Implementation Partner)", "Week 2", "Data Migration",
        "We're confident the migration will complete without any downtime this time.",
        "over_confidence"),
    Statement("Tom Becker", "Business Sponsor", "Week 1", "Budget",
        "Budget is not a concern at this stage, we'll figure out overruns later if they happen.",
        "escalation_avoidance"),
    Statement("Anita Desai", "QA Lead", "Week 2", "Test Coverage",
        "We found three P1 defects in the ECO workflow but they're being tracked internally for now.",
        "escalation_avoidance"),

    # ---- Week 3 ----
    Statement("Raj Malhotra", "Engineering Lead", "Week 3", "Aras Integration",
        "We've fully resolved the sync issue and don't anticipate any further blockers.",
        "over_confidence"),
    Statement("Priya Nair", "Vendor PM (Implementation Partner)", "Week 3", "Data Migration",
        "There were a few hiccups in the trial run, but the core team is on it, nothing major.",
        "hedging"),
    Statement("Tom Becker", "Business Sponsor", "Week 3", "Go-Live Timeline",
        "I understand engineering wants a two-week buffer, but leadership already committed to Nov externally.",
        "conflicting_priorities"),
    Statement("Anita Desai", "QA Lead", "Week 3", "Test Coverage",
        "Honestly, at this rate we won't finish full regression before go-live, but I'll let the PM decide if that's raised.",
        "escalation_avoidance"),

    # ---- Week 4 ----
    Statement("Raj Malhotra", "Engineering Lead", "Week 4", "Aras Integration",
        "Root cause was actually a data quality issue from the legacy ERP export, not our integration layer.",
        "deflection"),
    Statement("Priya Nair", "Vendor PM (Implementation Partner)", "Week 4", "Data Migration",
        "Migration dry-run is complete and validated end to end.",
        None),
    Statement("Tom Becker", "Business Sponsor", "Week 4", "Go-Live Timeline",
        "We are on track and I don't foresee any reason to move the date.",
        "over_confidence"),
    Statement("Anita Desai", "QA Lead", "Week 4", "Test Coverage",
        "Regression suite is 92% complete with a clear plan for the remaining 8%.",
        None),
]


def to_dicts() -> list[dict]:
    return [s.__dict__ for s in REPORTS]


def save(path: str = None):
    path = path or os.path.join(os.path.dirname(__file__), "synthetic_reports.json")
    with open(path, "w") as f:
        json.dump(to_dicts(), f, indent=2)
    print(f"Saved {len(REPORTS)} statements to {path}")


if __name__ == "__main__":
    save()
