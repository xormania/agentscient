# Retained interface and unit1a artifacts

Original producer: GPT-6, dispatch `20260906T111519Z-code-codex-dce07d`.
The launcher retained the seven-document result in combined source commit
`f15ca22c7d0cedb14f8d299fd61d7135f04ea9bc`; the read-only Git directory
prevented the two requested producer commits. These are the original separate
patches and messages, preserved as evidence without rewriting that history.

Capture measured at 2026-09-06T11:47:36.841175+00:00.
Each regular artifact was copied byte-for-byte from the canonical dispatch out directory.
The original invalid envelope remains in its dispatch record. This archive
does not change its verdict, approve the source, or admit a runtime.

| File | Bytes | SHA-256 |
|---|---:|---|
| `01-interface-fix.patch.b64` | 7055 | `3cd7a4838d4181870a3fe67aa89c82cecfa4d809059449ca20c3441d47fc6477` |
| `01-COMMIT_MSG` | 873 | `30ea73a9f71b6a377b4bafc1cae327ec10e9c963d308a2de81cd493d20a1672b` |
| `02-unit1a.patch.b64` | 37212 | `dad3831caa7b480fdb01458bdd60d252892bbee72b23b804989e119ce179c919` |
| `02-COMMIT_MSG` | 1065 | `858833ad25591105db06f170ef07186d9a0fd2bfab6ef33927f6c3764ae93f33` |

The two patches use standard Base64 storage so their significant blank-context
spaces survive the repository whitespace checks. Table sizes and hashes name
the decoded original bytes. Decode with `base64 --decode FILE.patch.b64`.
A byte-for-byte encode/decode comparison passed for both original patches;
the commit-message files remain plain text. The initial raw capture remains
in commit c35ed64, preserving the archive history.
