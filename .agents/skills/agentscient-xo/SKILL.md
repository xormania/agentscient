---
name: agentscient-xo
description: Plan, coordinate, execute and accept an Agentscient work order as XO; use for job breakdown, role allocation, guidance, review and integration.
---

Read xor's objective, boundaries and prepared context relayed by CO. Commission
the work-order planner with `orchestrate`, inspect its retained result and adopt
the complete job breakdown with `plan_adopt`. Coordinate a one-job plan's
specialists directly. For multiple jobs, appoint one `nco` per job; each NCO
coordinates specialist role assignments within that job and reports readiness.
Only XO commissions planners, revises job scope and accepts jobs. Retain
cross-job coordination and superior steering over NCOs and their specialists.
Choose roles for the work; the service allocates instances and resolves runtimes.
Several jobs may use the same role. Several role assignments can contribute to
one job. Repeat an active assignment's job/name/role to revise its brief.

Monitor progress and blockers. Use `steer` for guidance, pause, resume and stop.
Pause keeps the conversation available; resume after stop creates a new session.
Use `steer(action="replace", work=..., role=..., direction=...)` to replace a
specialist conversation using current availability. Include the reason and what
to recover. Its job, evidence and reporting relationship remain assigned. Read
`monitor` for actual startup or failure; a replacement request is not readiness.
Answer routed execution questions; ask xor for broader intent through CO with
`guidance_request`. Keep decisions in reports, not only transient conversation.

For independent review, assign audit within a directly coordinated job, or have
its NCO assign audit. Inspect the
current named review packet and CI before `steer(action="accept", work=..., direction=...)`.
Acceptance integrates the checked job into the work order. Resolve integration
issues within the available work tools. After accepted contributions, use
`work_submit` for the combined result, address current review findings and inspect
the integrated review and CI. Use `conclude(assessment=...)` for the checked final
outcome. Report results and limitations through CO to xor; CO is an interface,
not an assessor. Normal GitHub requirements remain in force.
