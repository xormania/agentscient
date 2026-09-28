---
name: infra
description: The local CI muscle — Gitea, act_runner and the lane image under ops/devlane/infra — what it is for and how it is composed up.
---

# infra — the local CI muscle

`ops/devlane/infra/` carries the compose file, the Gitea and act_runner
images, the lane image and the containment lint that the House built to
spend CI minutes locally. Here it is present and inert: this repository
runs its checks on its own self-hosted GitHub runners (`AGENTS.md`
§Standing rulings), and nothing composes the stack up until a unit
needs it.

```
ops/devlane/infra/compose.yml
ops/devlane/infra/build-lane.sh
ops/devlane/infra/containment-lint.sh
ops/devlane/infra/pins.env
```

The pins file names every image by digest; `containment-lint.sh` refuses
a compose file that mounts the docker socket or a host home. The House's
infra suites did not cross; that absence is declared in `ops/README.md`.
