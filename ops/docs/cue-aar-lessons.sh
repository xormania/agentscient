#!/usr/bin/env bash
# Each case: a CUE shape, a document that MUST be rejected, and what
# actually happened. Run it; do not remember it.
set -u

# Everything below is scratch: build it in a throwaway directory so the
# script can be run from anywhere without littering the tree it lives in.
WORK=$(mktemp -d "${TMPDIR:-/tmp}/cue-aar-XXXXXX")
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
say() { printf '%-46s %s\n' "$1" "$2"; }
try() {  # try <schema> <doc> -> "accepted" | first error line
  if cue vet -d '#D' "$1" "$2" >/dev/null 2>&1; then echo "ACCEPTED"
  else cue vet -d '#D' "$1" "$2" 2>&1 | head -1; fi
}

cat > bad.json <<'J'
{"h": {"version": "3.0.0", "iso": {"m": "flags", "obs": {"v": "2.1.4"}}}}
J
cat > good.json <<'J'
{"h": {"version": "2.1.4", "iso": {"m": "flags", "obs": {"v": "2.1.4"}}}}
J
cat > omitted.json <<'J'
{"h": {"version": "2.1.4", "iso": {"m": "flags", "obs": {}}}}
J

cat > a-hidden-disj.cue <<'C'
package m
#Obs: close({v: string})
#ByF: {m: "flags", home?: string}
#ByH: {m: "home", home: string}
#Iso: #ByF | #ByH
#H: close({version: string, iso: #Iso & {obs: #Obs}})
#C: close({h: #H})
#D: #C & {_v: string, h: version: _v, h: iso: obs: v: _v}
C
cat > b-hidden-nodisj.cue <<'C'
package m
#Obs: close({v: string})
#Iso: close({m: "flags" | "home", home?: string, obs: #Obs})
#H: close({version: string, iso: #Iso})
#C: close({h: #H})
#D: #C & {_v: string, h: version: _v, h: iso: obs: v: _v}
C
cat > c-direct-disj.cue <<'C'
package m
#Obs: close({v: string})
#ByF: {m: "flags", home?: string}
#ByH: {m: "home", home: string}
#Iso: #ByF | #ByH
#H: close({version: string, iso: #Iso & {obs: #Obs}})
#C: close({h: #H})
#D: #C & {h: version: string, h: iso: obs: v: h.version}
C
cat > d-direct-nodisj.cue <<'C'
package m
#Obs: close({v: string})
#Iso: close({m: "flags" | "home", home?: string, obs: #Obs})
#H: close({version: string, iso: #Iso})
#C: close({h: #H})
#D: #C & {h: version: string, h: iso: obs: v: h.version}
C
cat > e-if-in-close.cue <<'C'
package m
#Obs: close({v: string})
#Iso: close({
	m: "flags" | "home"
	home?: string
	obs: #Obs
	if m == "home" { home: string }
})
#H: close({version: string, iso: #Iso})
#C: close({h: #H})
#D: #C & {h: iso: obs: v: string, h: iso: m: "flags" | "home"}
C

echo "A. does the constraint reject the mismatching document?"
say "  hidden field + disjunction"      "$(try a-hidden-disj.cue bad.json)"
say "  hidden field, no disjunction"    "$(try b-hidden-nodisj.cue bad.json)"
say "  direct reference + disjunction"  "$(try c-direct-disj.cue bad.json)"
say "  direct reference, no disjunction" "$(try d-direct-nodisj.cue bad.json)"
echo
echo "B. and does the matching document still validate?"
say "  direct reference + disjunction"  "$(try c-direct-disj.cue good.json)"
say "  direct reference, no disjunction" "$(try d-direct-nodisj.cue good.json)"
echo
echo "C. a required field the constraint can now fill in for you"
say "  obs.v omitted entirely"          "$(try d-direct-nodisj.cue omitted.json)"
echo
echo "D. a comprehension inside close(), with the struct named twice"
say "  if m == \"home\" inside close()"  "$(try e-if-in-close.cue good.json)"
