"""The test kit: one world, one command runner, one fake registry, and
the case pattern on them. The contract is docs/tests.md.

Import from the repository root, the working directory every suite runs
in: ``from ops.testkit import World, run, refusal_wire``. There is no
other way in.
"""

from .cases import Mutant, RefusalCase, calibrate, refusal_wire, run_table, sidebyside
from .command import NotOnTheWire, Refusal, Result, Timeout, run
from .fakes import Tools
from .world import (
    PlantFailed,
    Watch,
    World,
    compare,
    hermetic_env,
    make_executable,
    plant_bytes,
    plant_text,
    require,
)

__all__ = [
    "Mutant",
    "NotOnTheWire",
    "PlantFailed",
    "Refusal",
    "RefusalCase",
    "Result",
    "Timeout",
    "Tools",
    "Watch",
    "World",
    "calibrate",
    "compare",
    "hermetic_env",
    "make_executable",
    "plant_bytes",
    "plant_text",
    "refusal_wire",
    "require",
    "run",
    "run_table",
    "sidebyside",
]
