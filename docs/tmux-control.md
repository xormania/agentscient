# Shared terminal control

Install tmux inside WSL2/Linux alongside your logged-in harnesses. Every managed
Claude, Codex and Grok session starts in an owned tmux terminal. A team uses a
separate tmux server, with a stable session name per collaborator; it does not
change your default tmux server, windows, configuration or unrelated terminals.

CO `direct` starts XO. XO `orchestrate` starts the roles it needs. These normal MCP
tools arrange role binding, runtime resolution and terminal creation automatically.
XO `steer` pauses, resumes or stops the named work. Pause leaves the native
conversation open for messages. Stop lets the harness exit; resuming after exit
creates a new native session with current runtime policy and preserved work context.

Operator MCP `session_start` / `session_stop` manage a registered member.
`terminal_status` returns the exact attach command and observed terminal presence;
`terminal_read` reads up to 500 recent lines. No shell commands, arbitrary target
names or keystroke injection are exposed through these tools. Programmatic
conversation uses the native protocol/channel transport, not terminal scraping.

Launches snapshot configuration and the caller's environment into a private,
owner-readable file, consumed and deleted at startup. This avoids stale credentials
or PATH values inherited from an older tmux server. Credentials do not appear in
the tmux command line. Capture uses the redacted runtime telemetry described in
[runtime telemetry](runtime-telemetry.md). Terminal scrollback itself is native
tmux data; treat the local terminal and state directory as private.

The terminal starts an isolated stdlib bootstrap directly, with Python and loader
overrides cleared by tmux before execution. It reads the private snapshot and
executes the application interpreter with that environment before importing any
application modules. Terminal identity variables come from the new pane. The
application consumes and deletes the snapshot. This uses tmux's documented
[multiple-argument direct execution](https://man.openbsd.org/tmux#COMMANDS), with
no intermediate shell or credential-bearing command arguments.

Duplicate starts retain an existing live session. An unexpected existing terminal
is reported for inspection instead of being killed. Startup errors are retained
and sent through the reporting chain. Terminal creation does not prove that a
native harness authenticated or that a message was acknowledged.

CI requires real tmux and runs persistent Claude/Codex/Grok protocol fixtures
through actual terminals, retaining their redacted communications and database
evidence. Locally, terminal tests explicitly skip if the environment cannot create
tmux sockets. Set `AGENTSCIENT_REQUIRE_TMUX=1` to make that condition fail.
Fixture acceptance is separate from authenticated native-vendor acceptance.
