"""The gate-kind registry: stages, evidence, outcomes and their effects.

Gate kinds are **data** (PLAN §6).  Tracked JSON under ``gate-kinds/`` is the
source of truth, ``wf init`` syncs it into the ``gate_kinds`` table, and a
work order pins ``(kind, version, spec_sha256)`` when it opens.

The pin is the authority, not the file.  The spec document is written to the
CAS at ``open`` and every later verb resolves the spec **from the CAS by the
pinned digest**, so an in-place edit of a registered version cannot change
how an already-open work order behaves — it is detected instead.

The engine never interprets an outcome value.  A spec declares each
outcome's effect as data — ``advance``, ``stay``, ``terminal``, or the name
of a stage to re-enter — and the engine applies the declared effect
mechanically (PLAN §3.5).
"""

from __future__ import annotations

from pathlib import Path

import canonical
from errors import Refusal

#: A leave_requires entry may name a receipt type, or a receipt type and a
#: check class: "receipt.check:security". PLAN §3.4 says a security stage is
#: "a stage whose spec requires receipts from checks of class security" and
#: leaves the spelling open; this is that spelling, and it keeps the engine
#: from knowing the word "security" at all.
REQUIREMENT_SEPARATOR = ":"


def split_requirement(requirement: str):
    """``receipt.check:security`` -> ``("receipt.check", "security")``."""
    if REQUIREMENT_SEPARATOR in requirement:
        etype, _, klass = requirement.partition(REQUIREMENT_SEPARATOR)
        return etype, klass
    return requirement, None


EFFECT_ADVANCE = "advance"
EFFECT_STAY = "stay"
EFFECT_TERMINAL = "terminal"
BUILTIN_EFFECTS = (EFFECT_ADVANCE, EFFECT_STAY, EFFECT_TERMINAL)


def _need(condition, precondition, **kwargs):
    if not condition:
        raise Refusal(precondition, **kwargs)


class Spec:
    """One validated gate-kind spec at one version."""

    def __init__(self, raw: dict, source: str = "<spec>"):
        self.raw = raw
        self.source = source
        self.validate()

    # -- validation --------------------------------------------------------

    def validate(self):
        raw, src = self.raw, self.source
        _need(isinstance(raw, dict), "gate-kind spec is a JSON object", actual=src)
        _need(
            isinstance(raw.get("kind"), str) and raw["kind"],
            "gate-kind spec names a kind", actual=src,
        )
        version = raw.get("version")
        _need(
            isinstance(version, int) and not isinstance(version, bool) and version >= 1,
            "gate-kind version is a positive integer",
            actual=f"{src}: {version!r}",
        )
        # Checks are validated before the stage loop reads them: the loop
        # derives declared classes from this list, and deriving from an
        # unvalidated shape turned the promised refusal into a TypeError.
        checks = raw.get("checks", [])
        _need(isinstance(checks, list), "checks is a list", actual=src)
        for check in checks:
            _need(
                isinstance(check, dict)
                and isinstance(check.get("name"), str) and check["name"]
                and isinstance(check.get("class"), str) and check["class"]
                and isinstance(check.get("argv"), list) and check["argv"]
                and all(isinstance(a, str) for a in check["argv"]),
                "every check has a name, a class and an argv template", actual=src,
            )
        declared_classes = {check["class"] for check in checks}

        stages = raw.get("stages")
        _need(
            isinstance(stages, list) and stages,
            "gate-kind spec declares at least one stage", actual=src,
        )
        names = []
        for stage in stages:
            _need(isinstance(stage, dict), "every stage is a JSON object", actual=src)
            name = stage.get("name")
            _need(
                isinstance(name, str) and name,
                "every stage has a name", actual=src,
            )
            _need(name not in names, "stage names are unique", actual=f"{src}: {name}")
            names.append(name)
            requires = stage.get("leave_requires", [])
            _need(
                isinstance(requires, list)
                and all(isinstance(r, str) and r for r in requires),
                "leave_requires is a list of evidence type names",
                actual=f"{src}: {name}",
            )
            for requirement in requires:
                etype, klass = split_requirement(requirement)
                if (etype == "receipt.check" and klass
                        and REQUIREMENT_SEPARATOR not in klass):
                    # A typo here is not a stage nobody can leave — it is a
                    # load-time refusal. Only receipt.check requirements are
                    # judged: check receipts come from this registry, so the
                    # class must exist in it; other receipt kinds carry their
                    # own class and owe the registry nothing.
                    _need(
                        klass in declared_classes,
                        "a check requirement's class is declared by one of"
                        " this gate kind's checks",
                        actual=f"{src}: {name}: {klass!r}",
                        expected=", ".join(sorted(declared_classes))
                                 or "(this gate kind declares no checks)",
                    )
                _need(
                    etype and (klass is None or (klass and REQUIREMENT_SEPARATOR
                                                 not in klass)),
                    "a class-qualified requirement names both a type and a class",
                    actual=f"{src}: {name}: {requirement!r}",
                    needed="exactly one colon, as in receipt.check:security,"
                           " or a plain type like receipt.green",
                )
            blocked = stage.get("blocked_by_open_markers", False)
            _need(
                isinstance(blocked, bool),
                "blocked_by_open_markers is a boolean", actual=f"{src}: {name}",
            )
            outcomes = stage.get("outcomes", {})
            _need(
                isinstance(outcomes, dict),
                "outcomes is an object mapping value to effect",
                actual=f"{src}: {name}",
            )
            for value, effect in outcomes.items():
                _need(
                    isinstance(value, str) and value,
                    "every outcome value is a non-empty string", actual=f"{src}: {name}",
                )
                _need(
                    isinstance(effect, str)
                    and (effect in BUILTIN_EFFECTS or effect in names or effect in
                         [s.get("name") for s in stages]),
                    "every outcome effect is advance, stay, terminal, or a declared stage",
                    actual=f"{src}: {name}.{value} -> {effect!r}",
                )
            actor = stage.get("actor")
            _need(
                actor is None or (isinstance(actor, str) and actor),
                "stage actor is a non-empty string when present", actual=f"{src}: {name}",
            )
            advance_to = stage.get("advance_to")
            _need(
                advance_to is None
                or (isinstance(advance_to, str)
                    and advance_to in [s.get("name") for s in stages]),
                "advance_to names a declared stage", actual=f"{src}: {name}",
            )
            seals = stage.get("seals_frozen_set", False)
            _need(
                isinstance(seals, bool),
                "seals_frozen_set is a boolean", actual=f"{src}: {name}",
            )
        for field in ("test_scope", "harness_scope"):
            value = raw.get(field, [])
            _need(
                isinstance(value, list) and all(isinstance(g, str) and g for g in value),
                f"{field} is a list of glob strings", actual=src,
            )
        toolchain = raw.get("toolchain_argv")
        _need(
            toolchain is None
            or (isinstance(toolchain, list) and toolchain
                and all(isinstance(a, str) for a in toolchain)),
            "toolchain_argv is a non-empty list of strings when present", actual=src,
        )

    # -- accessors ---------------------------------------------------------

    @property
    def kind(self) -> str:
        return self.raw["kind"]

    @property
    def version(self) -> int:
        return self.raw["version"]

    @property
    def sha256(self) -> str:
        return canonical.digest(self.raw)

    @property
    def stage_names(self) -> list:
        return [s["name"] for s in self.raw["stages"]]

    @property
    def first_stage(self) -> str:
        return self.raw["stages"][0]["name"]

    @property
    def test_scope(self) -> list:
        return list(self.raw.get("test_scope", []))

    @property
    def harness_scope(self) -> list:
        return list(self.raw.get("harness_scope", []))

    @property
    def toolchain_argv(self):
        return self.raw.get("toolchain_argv")

    @property
    def checks(self) -> list:
        return list(self.raw.get("checks", []))

    def stage(self, name) -> dict:
        for stage in self.raw["stages"]:
            if stage["name"] == name:
                return stage
        raise Refusal(
            "stage is declared by the gate kind",
            actual=repr(name),
            expected=", ".join(self.stage_names),
            needed=f"a stage of {self.kind}@{self.version}",
        )

    def leave_requires(self, name) -> list:
        return list(self.stage(name).get("leave_requires", []))

    def outcomes(self, name) -> dict:
        return dict(self.stage(name).get("outcomes", {}))

    def actor(self, name):
        return self.stage(name).get("actor")

    def seals_frozen_set(self, name) -> bool:
        return bool(self.stage(name).get("seals_frozen_set", False))

    def blocked_by_open_markers(self, name) -> bool:
        return bool(self.stage(name).get("blocked_by_open_markers", False))

    def check(self, name):
        """A registered check by name, refusing with the ones that exist."""
        for entry in self.checks:
            if entry["name"] == name:
                return entry
        raise Refusal(
            "the check is registered by the gate kind",
            actual=repr(name),
            expected=", ".join(sorted(c["name"] for c in self.checks)) or "(none)",
            needed=f"a check declared by {self.kind}@{self.version}",
        )

    def next_stage(self, name):
        """The stage a plain ``advance`` enters from ``name``.

        Positional order by default; ``advance_to`` overrides it, which is
        how a fix stage returns to review rather than falling through to
        whatever happens to be written next in the file.
        """
        stage = self.stage(name)
        if stage.get("advance_to"):
            return stage["advance_to"]
        names = self.stage_names
        index = names.index(stage["name"])
        return names[index + 1] if index + 1 < len(names) else None


def load_specs(directory: Path) -> dict:
    """Every spec file in ``directory``, keyed by ``(kind, version)``."""
    directory = Path(directory)
    if not directory.exists():
        raise Refusal(
            "the gate-kind registry directory exists",
            actual=str(directory),
            needed="a gate-kinds/ directory holding the registry",
        )
    specs = {}
    for path in sorted(directory.glob("*.json")):
        try:
            raw = canonical.loads(path.read_bytes())
        except ValueError as exc:
            raise Refusal(
                "every gate-kind file is JSON", actual=path.name, needed=str(exc)
            ) from None
        spec = Spec(raw, source=path.name)
        key = (spec.kind, spec.version)
        if key in specs:
            raise Refusal(
                "gate-kind versions are registered once",
                actual=f"{spec.kind}@{spec.version} in {path.name} and {specs[key].source}",
                needed="one file per (kind, version)",
            )
        specs[key] = spec
    return specs


def sync(store, specs: dict, now: str) -> None:
    for spec in specs.values():
        store.upsert_gate_kind(
            spec.kind, spec.version, canonical.dumps(spec.raw), spec.sha256, now
        )


def latest(specs: dict, kind: str) -> Spec:
    versions = [v for (k, v) in specs if k == kind]
    if not versions:
        known = sorted({k for (k, _) in specs})
        raise Refusal(
            "the gate kind is registered",
            actual=kind,
            expected=", ".join(known) or "(none)",
            needed="a gate kind with a file in gate-kinds/",
        )
    return specs[(kind, max(versions))]
