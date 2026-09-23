"""Planted faults for session_adapters/grok.py (sessions-lever.md, slice 2).

Each mutant is a literal edit to a copy of the subject, never the tree;
the kit's Mutant applies the anchor in an archive copy. Every row of
test_session_adapters_grok.py must stay green on the clean subject, and
the rows named in each note must go red on its mutant:

    python3 ops/testkit/cases.py calibrate --subject ops/conductor/tools/session_adapters/grok.py \\
        --mutants ops/conductor/tests/session_adapters_grok_faults.py \\
        --command "python3 -m unittest discover -s ops/conductor/tests -p test_session_adapters_grok.py"

Anchored on the subject at bf924ee7 (#277). An anchor that no longer
matches once refuses class anchor; re-measure it against the subject.
"""

from ops.testkit import Mutant

SUBJECT = "ops/conductor/tools/session_adapters/grok.py"

MUTANTS = [
    Mutant(
        "M-permission-allowed",
        SUBJECT,
        'outcome = ({"outcome": "selected", "optionId": reject} if reject',
        'outcome = ({"outcome": "selected", "optionId": "allow-once"} if reject',
        "the permission is answered allow-once (grok-observe-permission, "
        "20260923T020912Z-review-codex-9d8b8c #19)",
    ),
    Mutant(
        "M-channel-argv-short",
        SUBJECT,
        'return ["--no-auto-update", "agent", "stdio"]',
        'return ["agent", "stdio"]',
        "the channel argv without --no-auto-update (#19)",
    ),
    Mutant(
        "M-cwd-own",
        SUBJECT,
        "return str(Path(named).absolute()) if named else os.getcwd()",
        "return os.getcwd()",
        "session/new sends the bridge's own cwd, not the member's worktree "
        "(grok-session-new-cwd, 0e's review of b3's grok.py)",
    ),
    Mutant(
        "M-servers-empty",
        SUBJECT,
        '"mcpServers": self.servers}',
        '"mcpServers": []}',
        "session/new names no MCP server (grok-session-new-mcp-named, "
        "11's review of fed6a4ce)",
    ),
    Mutant(
        "M-ready-not-read",
        SUBJECT,
        'return f"tool {common.SERVER} ready"',
        'return "activity active"',
        "the coordination server's ready status is not read as the tool "
        "(grok-session-new-mcp-named)",
    ),
]
