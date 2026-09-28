### 3.1 Closure — `closure.cue`, `closure.py`, `closure.json`
`#ClosureIndex: close({contracts: [...#Row, ...]})`. `#Row: close({path: #NonEmpty, consumer: #NonEmpty | #DeclaredAbsent, fixture: #NonEmpty | #DeclaredAbsent})`. `closure.py check` walks `git ls-files '*.cue' 'ops/conductor/*-lever.md'`, diffs against the index, vets the index as `#ClosureIndex`, and for every closed row subprocess-checks that the fixture path exists. Cue missing: class `cue-missing`, exit 2. Cue version other than `#CueVersion`: `cue-version`. CLI stdlib only.
### 3.2 Job-kind manifests — `manifest.cue`
Reuse `#NonEmpty`, `#Digest`, `#DeclaredAbsent`, `#HarnessName`, `#IsolationObserved` from `context.cue`. New: `#CueVersion`, `#Section`, `#HarnessFacts`, `#Custody`, `#Manifest`, `#Launchable`, `#ReadProbe`, one closed definition per kind.
| kind | required slots | optional (max) | writes |
|---|---|---|---|
| `author-tests` | scope, brief, diff | plan (1), previous (1), report (1), findings (2) | snapsho
