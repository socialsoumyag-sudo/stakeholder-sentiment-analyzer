"""
Privacy Layer — Pseudonymization
---------------------------------
Core principle: real identities (names, emails, phone numbers) never leave
the local machine. Everything sent to the LLM uses stable, anonymous
identifiers (Stakeholder_A, Stakeholder_B, ...). The mapping back to real
identities is held ONLY locally, encrypted at rest is recommended for real
deployments (see note at bottom).

This also does generic PII scrubbing on free text (emails, phone numbers,
employee IDs) so accidental PII inside statement text doesn't leak to the
LLM either.
"""

import json
import os
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional

MAPPING_FILE = os.path.join(os.path.dirname(__file__), "identity_mapping.json")

# Generic PII patterns caught in free text regardless of whether the person
# is a known stakeholder. Conservative regexes -- false positives (over-redacting)
# are the safe failure mode here, not false negatives.
PII_PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone": re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b'),
    "employee_id": re.compile(r'\b[A-Z]{2,4}-?\d{4,8}\b'),
}


@dataclass
class IdentityMap:
    """Bidirectional mapping between real names and pseudonyms.
    Persisted locally only -- this file must NEVER be committed to git
    or sent anywhere. Add identity_mapping.json to .gitignore.
    """
    real_to_pseudo: dict = field(default_factory=dict)
    pseudo_to_real: dict = field(default_factory=dict)
    _counter: int = 0

    def get_or_create(self, real_name: str) -> str:
        if real_name in self.real_to_pseudo:
            return self.real_to_pseudo[real_name]

        letter = chr(65 + self._counter)  # A, B, C, ...
        pseudo = f"Stakeholder_{letter}"
        self._counter += 1

        self.real_to_pseudo[real_name] = pseudo
        self.pseudo_to_real[pseudo] = real_name
        return pseudo

    def resolve(self, pseudo: str) -> str:
        return self.pseudo_to_real.get(pseudo, pseudo)

    def save(self, path: str = None):
        path = path or MAPPING_FILE
        with open(path, "w") as f:
            json.dump({
                "real_to_pseudo": self.real_to_pseudo,
                "pseudo_to_real": self.pseudo_to_real,
                "_counter": self._counter,
            }, f, indent=2)

    @classmethod
    def load(cls, path: str = None) -> "IdentityMap":
        path = path or MAPPING_FILE
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            data = json.load(f)
        return cls(
            real_to_pseudo=data.get("real_to_pseudo", {}),
            pseudo_to_real=data.get("pseudo_to_real", {}),
            _counter=data.get("_counter", 0),
        )


def scrub_pii_from_text(text: str) -> tuple[str, list[dict]]:
    """Redacts emails/phones/employee-IDs found INSIDE free text (not the
    speaker field itself, which is handled by pseudonymization above).
    Returns (scrubbed_text, list of what was redacted for audit purposes).
    """
    redactions = []
    scrubbed = text

    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(scrubbed)
        for match in matches:
            # Use a stable hash-based placeholder so the same PII value
            # redacts consistently within one document (helps the model
            # still reason about "the same person mentioned twice")
            placeholder = f"[REDACTED_{pii_type.upper()}_{hashlib.md5(match.encode()).hexdigest()[:6]}]"
            scrubbed = scrubbed.replace(match, placeholder)
            redactions.append({"type": pii_type, "placeholder": placeholder})

    return scrubbed, redactions


def pseudonymize_statements(statements: list[dict], identity_map: IdentityMap) -> tuple[list[dict], list[dict]]:
    """Takes raw statements (with real stakeholder names + free text that may
    contain PII) and returns pseudonymized statements safe to send to the LLM,
    plus an audit trail of what was redacted.
    """
    pseudonymized = []
    audit_trail = []

    for stmt in statements:
        pseudo_name = identity_map.get_or_create(stmt["stakeholder"])
        scrubbed_text, redactions = scrub_pii_from_text(stmt["text"])

        pseudonymized.append({
            **stmt,
            "stakeholder": pseudo_name,
            "text": scrubbed_text,
        })

        if redactions:
            audit_trail.append({
                "original_stakeholder": stmt["stakeholder"],  # kept in LOCAL audit log only
                "pseudo_stakeholder": pseudo_name,
                "redactions": redactions,
            })

    return pseudonymized, audit_trail


def rehydrate_output(output: dict, identity_map: IdentityMap) -> dict:
    """Takes LLM output (which references Stakeholder_A, etc.) and swaps
    pseudonyms back to real names for local display ONLY. This should be
    the very last step before showing something to the human user --
    never re-send rehydrated content back to the LLM.
    """
    output_str = json.dumps(output)
    for pseudo, real in identity_map.pseudo_to_real.items():
        output_str = output_str.replace(pseudo, real)
    return json.loads(output_str)


if __name__ == "__main__":
    # Quick self-test
    im = IdentityMap()
    statements = [
        {"stakeholder": "Raj Malhotra", "role": "Engineering Lead", "week": "Week 1",
         "topic": "Test", "text": "Contact me at raj.malhotra@otis.com if issues persist."},
        {"stakeholder": "Tom Becker", "role": "Sponsor", "week": "Week 1",
         "topic": "Test", "text": "Call vendor at 555-123-4567 for updates."},
    ]
    pseudo_stmts, audit = pseudonymize_statements(statements, im)
    print("Pseudonymized:", json.dumps(pseudo_stmts, indent=2))
    print("\nAudit trail (LOCAL ONLY, never sent anywhere):", json.dumps(audit, indent=2))

    fake_llm_output = {"summary": f"{pseudo_stmts[0]['stakeholder']} raised a concern."}
    print("\nRehydrated for display:", rehydrate_output(fake_llm_output, im))
