# receipt/ — the engine's receipt modules, verbatim

`receipts.py`, `canonical.py`, `gitio.py` and `errors.py` are copied byte
for byte from the previous repository's workflow engine at its commit
99334f7, under hand grant 89 (owner, 2026-09-11: extract rather than
rewrite). Their `Source:` trailers name that path and commit. They are
loaded by path from `../receipt.py`, the adapted lever, and nothing here
is edited: an adaptation belongs in the lever, and the extraction
checklist beside the work order names each one.

What the lever uses: `canonical` (digests, canonical JSON, the wire time),
`receipts.run` (a wrapped command with both outputs captured) and
`errors.Refusal` (mapped to this lane's wire). What waits for the later
frozen-set gate: `receipts.Scope`, the manifest functions and
`toolchain_string`. What is dead here and kept for fidelity: the `gitio`
functions that take the engine's store as an argument.

`head_sha` in a receipt is the sha256 of the commit id's hex: the contract
wants a 64-hex digest and git here gives 40. `verify` recomputes it the
same way, so the two always agree or the tree has moved.
