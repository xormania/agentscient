# Test ruling — 2026-09-05

GPT-6 rules on the [Daybreak skeptic report](mcp-test-skeptic-2026-09-05.md)
against tests at `a8a85297605136adc5573deeef36b187c03d8335`, SHA-256
`f1d187b85dbde358dcc503de1b714a89ea00c0e697436d926825cdb3d80e5a67`.
The test producer was Grok 4.6; the finder was gpt-daybreak-blue-latest.
This adjudicator produced neither the tests nor these findings.

All seven findings are UPHELD and require one focused test correction round
before implementation. Original priorities are retained in the report.

| Finding | Evidence checked | Required correction |
| --- | --- | --- |
| 1: byte-fit and pagination | No 8192 assertion in the file; the first two pages need only form a prefix of the eight entries | Measure canonical bytes, exercise omission order and the note-removal fallback, and follow continuation until all entries are accounted for |
| 2: no origination | New parity test compares only one record; inherited invoke/load helpers contain no filesystem snapshot check | Compare contents and names across the owned config, sources, directories and HOME before/after all three reads |
| 3: non-happy MCP parity | New v2 domain refusals are CLI-only; existing MCP error-line assertion uses v1 lane_record | Compare v2 isError/refusal text and unknown/unavailable readings with CLI and applicable resources |
| 4: per-ID states | Changes test uses two valid records or a wholly missing/unavailable store | Plant readable, missing and malformed records together; check the partitions and the returned checkpoint |
| 5: registry predicates/cards | Valid row plus withheld/slot variants do not isolate adapter, role, snapshot or prompt | Small one-field variants and bounded card normalization assertions, including the malformed-key rule |
| 6: metadata coverage | Metadata matrix omits template listing and v2 calls | Verify ignored object metadata and refused non-object metadata on those paths |
| 7: v1 payload preservation | Only lane_record is compared under both config versions | Compare the other three existing reads, including unchanged brief omissions |

Reproduction: read the cited test sections and inherited fixture methods
`invoke`, `load_query` and `assert_refusal`; search the test for `8192`,
`before`, `source_bytes`, `_tree_files`, `v1_payload` and `_meta`.
This is an assertion-level ruling, not a claim that an implementation
mutant was executed. Root independently ran the 16 tests: 13 methods were
red (18 failure reports including subtests), three methods green; Ruff passed.

The author's earlier P3 note about inability to plant a page boundary does
not hold: the contract specifies the canonical JSON encoding, so an
independent fixture can measure it with the standard JSON encoder. A valid
8191-byte frame-plus-note and 8297-byte result after a reduced entry were
already reproduced during contract admission. No production encoder read
is needed. Successful finding pages have the 8192-byte bound; an unavailable
reading with `page:null` retains the inherited 16384-byte whole-query bound.

Use small fixtures and reuse helpers; the correction is about missing
behavior assertions. Preserve the existing tests and the original report.
The skeptic runs once; the conductor will verify the corrected oracle and
the implementation remains a different producer.
