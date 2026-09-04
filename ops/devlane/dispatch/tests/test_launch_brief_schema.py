"""Harnesses whose argv carries no schema get it appended to the brief.

Written from CONTRACT.md §Template values and the lane-fix batch plan
§3.6: after render, for every harness whose argv does not carry
``--json-schema`` (codex and grok), the launcher appends the envelope
schema to ``prompt.txt``. ``brief.sha256`` digests the bytes handed
over, appended section included. Claude keeps ``--json-schema`` and
gets no appended section. launch.py was not read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import launch_support as ls

ENVELOPE_PY = ls.APP.parents[0] / "task" / "envelope.py"

SCHEMA_SECTION_LEAD = (
    "The envelope shape, as JSON Schema. Every key in `required` is "
    "present; no other top-level key; the types are exact (findings "
    "are objects, counts are integers, artifacts is an object of "
    "strings):"
)


class _BriefSchema(ls._TempLaunch):
    def schema_json(self):
        launch = self.load_launch()
        raw = getattr(launch, "ENVELOPE_SCHEMA_JSON", None)
        if isinstance(raw, str) and raw.strip():
            json.loads(raw)
            return raw
        envmod = ls.load_path(self, ENVELOPE_PY, "brief_schema_envelope")
        schema = getattr(envmod, "ENVELOPE_SCHEMA", None)
        self.assertIsInstance(
            schema, dict,
            "ENVELOPE_SCHEMA_JSON or envelope.ENVELOPE_SCHEMA must exist",
        )
        return json.dumps(schema)

    def handed_brief(self, rec, witness, *, harness):
        job_dir = Path(rec["snapshot"]["root"]).parent
        path = job_dir / "prompt.txt"
        self.assertTrue(path.is_file(), f"prompt.txt missing under {job_dir}")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text, "prompt.txt is empty")
        if harness == "grok":
            received = witness.get("prompt_text") or ""
        else:
            received = witness.get("stdin") or ""
        self.assertTrue(
            received,
            f"{harness} must receive the rendered brief "
            f"(stdin/prompt_text empty; prompt.txt has {len(text)} bytes)",
        )
        return text, received, path

    def assert_digest_matches_file(self, rec, path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(
            rec["brief"]["sha256"], digest,
            "brief.sha256 digests the bytes handed over, schema section "
            "included",
        )


class CodexAndGrokBriefsEndWithTheEnvelopeSchema(_BriefSchema):
    """Codex (stdin) and grok (prompt_text) carry ENVELOPE_SCHEMA_JSON."""

    def test_codex_brief_ends_with_the_envelope_schema(self):
        rec, witness, *_ = self.launch_ok(
            job="plan", harness="codex", stage="plan",
        )
        schema = self.schema_json()
        text, received, path = self.handed_brief(
            rec, witness, harness="codex",
        )
        self.assertIn(SCHEMA_SECTION_LEAD, received)
        self.assertIn(schema, received)
        self.assertIn(SCHEMA_SECTION_LEAD, text)
        self.assertIn(schema, text)
        self.assertTrue(
            received.rstrip().endswith(schema.rstrip())
            or text.rstrip().endswith(schema.rstrip()),
            "the envelope schema is the end of the handed brief",
        )
        self.assert_digest_matches_file(rec, path)
        argv = [str(a) for a in witness["argv"]]
        self.assertNotIn("--json-schema", argv)

    def test_grok_brief_ends_with_the_envelope_schema(self):
        rec, witness, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        schema = self.schema_json()
        text, received, path = self.handed_brief(
            rec, witness, harness="grok",
        )
        self.assertIn(SCHEMA_SECTION_LEAD, received)
        self.assertIn(schema, received)
        self.assertIn(SCHEMA_SECTION_LEAD, text)
        self.assertIn(schema, text)
        self.assertTrue(
            received.rstrip().endswith(schema.rstrip())
            or text.rstrip().endswith(schema.rstrip()),
            "the envelope schema is the end of the handed brief",
        )
        self.assert_digest_matches_file(rec, path)
        argv = [str(a) for a in witness["argv"]]
        self.assertNotIn("--json-schema", argv)


class ClaudeBriefCarriesNoSchemaSection(_BriefSchema):
    """Claude keeps --json-schema on argv and gets no appended section."""

    def test_claude_brief_carries_no_schema_section(self):
        rec, witness, *_ = self.launch_ok(
            job="plan", harness="claude", stage="plan",
        )
        text, received, path = self.handed_brief(
            rec, witness, harness="claude",
        )
        self.assertNotIn(SCHEMA_SECTION_LEAD, received)
        self.assertNotIn(SCHEMA_SECTION_LEAD, text)
        argv = [str(a) for a in witness["argv"]]
        self.assertIn("--json-schema", argv)
        self.assert_digest_matches_file(rec, path)
