adversarial audit envelope, record 20260911T225002Z-review-grok-a00d0e

{
  "artifacts": {},
  "counts": {
    "opinions": 0,
    "p1": 0,
    "p2": 1,
    "p3": 0
  },
  "findings": [
    {
      "claim": "declared (.dev/ladder-inputs/scope-item31-20260911.md:40): Before the ladder advances, the driver checks: findings is a list of item 2 shapes; counts agree with findings; verdict agrees with item 2; artifacts is empty. A violation stops the ladder with a refusal of class `envelope` on the wire naming the field, recorded as the stop reason; it is never retried as a flake.; practiced (ops/conductor/ladder-lever.md:118): If its stopped dispatch record is now closed with an accepted envelope, resume consumes and lands it without relaunching. Otherwise it relaunches that stage once. Line 129 adds never retried as a flake without amending that standing resume rule, so a schema-accepted check-tests envelope that fails the item-2 shape checks is consumed and landed, or relaunched as a flake.",
      "reproduce": "python3 -c \"from pathlib import Path; t=Path('ops/conductor/ladder-lever.md').read_text(); assert 'resume consumes and lands it' in t and 'Otherwise it relaunches that stage once.' in t and 'never retried as a flake' in t\"",
      "severity": "p2",
      "where": "ops/conductor/ladder-lever.md:118"
    }
  ],
  "job": "adversarial-review",
  "note": "Slice 1 contracts and document pins measured against the eight Contract items. Item 3 is not unique in ladder-lever.md: standing resume still lands or relaunches. Items 1, 2, 4, 5, 6 and 8 hold of the landed contract prose; jobs.json, ladder.py, write_path.py and launch.py are later slices. Item 7 one-stderr-line-then-stopped-line is already open as 20260911T224145Z-review-codex-c5fc8b#3 and is not re-raised; the frozen envelope/custody pins require that dual last-output. Security P1s against the plan (unresolved quote locations; eight-verb list) are not this slice's contract text: the role row does not enumerate those verbs, and item 2 requires carrying quotes rather than resolving them to files. Did not read the session store. Graft saved ~1587499 tokens.",
  "spend": {
    "harness": "grok",
    "out": 54420,
    "runs": 1,
    "total": 1443735
  },
  "stamp": {
    "ended": null,
    "ref": "13c38525e7a4c1840d9b6f2362f9d2d5d18e2839",
    "started": null
  },
  "status": "ok",
  "verdict": "changes"
}
