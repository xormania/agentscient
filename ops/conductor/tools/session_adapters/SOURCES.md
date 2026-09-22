# Sources — session_adapters

Adapted from `/home/scientdb/projects/poc/multi-harness-proof` at `a944f31`.
That repository's own license, verbatim:

```
MIT License

Copyright (c) 2026 xor

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Manifest

Each adapted function beside its origin, `file:line` at `a944f31`.

| here | origin | what was taken |
|---|---|---|
| `framing.py: Parser.feed` | `mhproof/rpc.py:68-92` (`RPC.read`) | the JSON-lines parse and the request/response id correlation, made synchronous: one line in, one frame out or a `Refused` naming the line |
| `framing.py: Refused` | `mhproof/rpc.py:6-9` (`RPCError`) | a typed exception carrying the reading, not the raw packet |
| `claude.py: Adapter.argv` | `mhproof/sessions.py:190-220` (`start`, the `ENTRY`/argv construction) | the shape of a fixed, non-operator launch argv for a native TUI window |
| `claude.py: Adapter.stop` | `mhproof/sessions.py:290-300` (`supervise`, the SIGINT-then-wait teardown) | signalling only a pid whose start ticks still match, never a stale one |
| `claude.py: Adapter.diagnostics` | `mhproof/sessions.py:74-85` (`Tmux.finish_peer`) | retaining a redacted terminal capture as evidence, by path |

## Not adapted

The proof's test-suite termination policy, its `queue.Queue`, `relay.py`,
`contract.py`, `suite.py`, and `controller()` (`mhproof/sessions.py:223-229`,
which calls `suite.run_suite`). None of these cross into the lane: the
termination policy and the queue are proof-harness test machinery; `relay.py`
and `contract.py` carry proof-only wire framing and tool-restriction prose
that this lane does not use; `suite.py` and `controller()` run the proof's
own multi-peer trial, not a managed lane session.
