---
name: agentscient-audit
description: Audit an Agentscient submitted revision independently; use for review findings, evidence and review decisions.
---

Read the objective, constraints and current review packet with `work_inspect`.
Review the immutable submitted source snapshot. Trace changed behavior and relevant
callers; use available diagnostics/checks where they answer a concrete concern.
Do not edit the producer's source or broaden the requested work.

Report findings with a reproducible scenario, location, impact and supporting
evidence. Separate demonstrated defects from questions or optional preferences.
Record the assessment with `review_record` for the inspected revision. If it changes,
refresh the packet and assess the new revision. An approval requires actual review;
successful CI alone is insufficient. Route blockers/questions through the supplied
reporting relationship. XO handles job acceptance and integration.
