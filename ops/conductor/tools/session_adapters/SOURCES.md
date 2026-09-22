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

Each adapted function beside its origin, `file:line` at `a944f31`. A row
is added in the commit that lands the function it names.

| here | origin | what was taken |
|---|---|---|
| `framing.py: Parser.feed` | `mhproof/rpc.py:68-92` (`RPC.read`) | the JSON-lines parse and the split of a received line into a request, a notification or a response correlated by id, made synchronous: one line in, one frame out or a `Refused` naming the line |
| `framing.py: Parser.sent` | `mhproof/rpc.py:37-52` (`RPC.request`, its `pending` book) | a response correlates only with a request this side sent |
| `framing.py: Refused` | `mhproof/rpc.py:6-9` (`RPCError`) | a typed exception carrying the reading, not the raw packet |

`Parser.answered`, the duplicate-request refusal and the id type check are
not in the proof; they come from the contract's framing faults.

## Not adapted

The proof's test-suite termination policy, its `queue.Queue`, `relay.py`,
`contract.py`, `suite.py`, and `controller()` (`mhproof/sessions.py:221-227`,
which calls `suite.run_suite`). None of these cross into the lane: the
termination policy and the queue are proof-harness test machinery; `relay.py`
and `contract.py` carry proof-only wire framing and tool-restriction prose
that this lane does not use; `suite.py` and `controller()` run the proof's
own multi-peer trial, not a managed lane session.
