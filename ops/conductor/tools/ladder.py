#!/usr/bin/env python3
"""Load the ladder driver's required configuration.

The orchestration instrument is implemented in the second ladder-driver run.
"""

from __future__ import annotations

import laneconf


def configuration() -> dict[str, str]:
    """Read every driver-owned required key through the shared reader."""
    return {
        "WORKTREE_ROOT": laneconf.get("WORKTREE_ROOT"),
        "ADDRESS_GROK": laneconf.get("ADDRESS_GROK"),
        "ADDRESS_CODEX": laneconf.get("ADDRESS_CODEX"),
        "ADDRESS_CLAUDE": laneconf.get("ADDRESS_CLAUDE"),
    }
