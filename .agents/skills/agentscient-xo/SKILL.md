---
name: agentscient-xo
description: Coordinate an Agentscient work order as XO; use for role allocation, guidance, review and integration.
---

Read CO's objective and boundaries, then use `orchestrate` for bounded named jobs
with the appropriate coder, audit, docs, research, test_writer or architect role.
Choose roles for the work; the service allocates instances and resolves runtimes.
Several jobs may use the same role. Repeat a work name/role to revise its brief.

Monitor progress and blockers. Use `steer` for guidance, pause, resume and stop.
Pause keeps the conversation available; resume after stop creates a new session.
Use `steer(action="replace", work=..., role=..., direction=...)` to replace a
specialist conversation using current availability. Include the reason and what
to recover. Its job, evidence and reporting relationship remain assigned. Read
`monitor` for actual startup or failure; a replacement request is not readiness.
Answer routed specialist questions; escalate broader intent to CO with
`guidance_request`. Keep decisions in reports, not only transient conversation.

For independent review, assign audit with the producer's job name. Inspect the
current named review packet and CI before `steer(action="accept", work=..., direction=...)`.
Acceptance integrates the checked job into the work order. Resolve integration
issues within the available work tools. After accepted contributions, use
`work_submit` for the combined result and report its evidence to CO. CO owns final
acceptance; normal GitHub requirements remain in force.
