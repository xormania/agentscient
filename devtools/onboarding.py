"""One versioned onboarding and skill source for every harness."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents/skills"
ROLES = {
    "co": (
        "Translate the user's intent into an authorized objective and boundaries; direct XO, assess the integrated result, and keep the user informed.",
        "agentscient-co",
    ),
    "xo": (
        "Organize named work across the specialist roles, route guidance, inspect evidence and integrate accepted contributions for CO.",
        "agentscient-xo",
    ),
    "coder": (
        "Implement the bounded change using installed framework features, preserve unrelated work, validate behavior and submit evidence.",
        "agentscient-coder",
    ),
    "audit": (
        "Independently review the submitted immutable revision against the objective; report reproducible findings and do not modify the producer's source.",
        "agentscient-audit",
    ),
    "docs": (
        "Keep user and developer documentation accurate to observed behavior, with runnable examples and explicit limitations.",
        "agentscient-docs",
    ),
    "research": (
        "Investigate the question using available sources, distinguish evidence from inference, and report a supported recommendation without source edits.",
        "agentscient-research",
    ),
    "test_writer": (
        "Design behavior tests that expose the relevant failure, cover meaningful boundaries, and retain measured results within test paths.",
        "agentscient-test-writer",
    ),
    "architect": (
        "Inspect existing capabilities, compare designs and tradeoffs, and record the smallest supported design within the documentation scope.",
        "agentscient-architect",
    ),
}
MATE = (
    "mate-system-information",
    "mate-php-environment-check",
    "mate-symfony-service-inspection",
    "mate-symfony-request-triage",
    "mate-symfony-profiler-debugging",
    "mate-symfony-dotenv-diagnostics",
)


def document(name):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name):
        raise ValueError("Choose a skill from onboard")
    path = (SKILLS / name / "SKILL.md").resolve()
    if not path.is_relative_to(SKILLS.resolve()):
        raise ValueError("Skill source leaves the repository catalog")
    content = path.read_text()
    header, body = content.split("---", 2)[1:]
    # Catalog frontmatter uses plain scalar names and plain/folded descriptions.
    # Keep the runtime stdlib-only; do not interpret arbitrary YAML objects.
    metadata = {}
    field = None
    for line in header.strip().splitlines():
        if line.startswith((" ", "\t")) and field:
            metadata[field] = (metadata[field] + " " + line.strip()).strip()
        elif ":" in line:
            field, value = line.split(":", 1)
            metadata[field] = "" if value.strip() in {">", ">-", "|", "|-"} else value.strip()
    if metadata.get("name") != name or not metadata.get("description"):
        raise ValueError("Invalid skill metadata")
    return {
        "name": name,
        "description": metadata["description"],
        "source": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "content": body.strip(),
    }


class Onboarding:
    def __init__(self, api):
        self.api = api

    def role(self):
        return self.api.commands.role(self.api.control.current())

    def catalog(self):
        role = self.role()
        if role not in ROLES:
            return []
        names = ["agentscient-context", ROLES[role][1]]
        tools = {row["name"] for row in self.api.tools()}
        if "framework_inspect" in tools:
            names += list(MATE) if role not in {"docs", "architect"} else [MATE[0], MATE[2]]
        catalog = []
        for name in names:
            skill = document(name)
            skill["guidance_sha256"] = hashlib.sha256(
                json.dumps(skill, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            catalog.append(skill)
        return catalog

    def startup(self):
        role = self.role()
        if role not in ROLES:
            return "Await an authorized role binding; work_context shows your current state."
        return (
            "Use the role-bound MCP tools. Call onboard once in a new session, after handover or a role change. "
            "It supplies the complete shared/role instructions and current brief. "
            "For subsequent work/context changes refresh work_context. "
            "Read only relevant skills not already supplied by onboard. Your role: " + role + "."
        )

    def onboard(self):
        role = self.role()
        catalog = self.catalog()
        if not catalog:
            raise ValueError("Await an authorized role binding")
        tools = [row["name"] for row in self.api.tools()]
        revision = hashlib.sha256(json.dumps([(r["name"], r["guidance_sha256"]) for r in catalog]).encode()).hexdigest()
        value = {
            "role": role,
            "responsibility": ROLES[role][0],
            "revision": revision,
            "shared": catalog[0]["content"],
            "role_instructions": catalog[1]["content"],
            "context": self.api.invoke("work_context", {}),
            "tools": tools,
            "skills": [
                {"name": row["name"], "description": row["description"], "loaded": index < 2}
                for index, row in enumerate(catalog)
            ],
        }
        self.api.store.event(
            self.api.member,
            "onboarding_delivered",
            role=role,
            revision=revision,
            skills=[row["name"] for row in catalog],
        )
        return value

    def read(self, name):
        skill = next((r for r in self.catalog() if r["name"] == name), None)
        if not skill:
            raise ValueError("Choose a skill from your current onboard catalog")
        self.api.store.event(
            self.api.member, "skill_loaded", role=self.role(), name=name, sha256=skill["sha256"],
            guidance_sha256=skill["guidance_sha256"], source=skill["source"]
        )
        return skill

