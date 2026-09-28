"""Content-addressed storage for receipt outputs, manifests and specs.

sha256-addressed, verify-before-write (PLAN §2): a digest that is already
present is read back and re-hashed before it is treated as a hit, so a
corrupted object is reported rather than silently reused.  Full outputs are
retained (D4).

Objects live at ``objects/<aa>/<digest>`` under the state root and are
tracked; the ``artifacts`` table is a queryable mirror rebuilt from the
chain and the object files.
"""

from __future__ import annotations

from pathlib import Path

import canonical
from errors import Integrity


class Cas:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise Integrity("digest is not a lowercase hex sha256", detail=digest)
        return self.root / digest[:2] / digest

    def put(self, data: bytes) -> str:
        """Store ``data``, returning its digest. Idempotent and verifying."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        digest = canonical.sha256_hex(data)
        path = self.path_for(digest)
        if path.exists():
            existing = path.read_bytes()
            if canonical.sha256_hex(existing) != digest:
                raise Integrity(
                    "stored object does not hash to its own name", detail=digest
                )
            if existing != data:
                raise Integrity("sha256 collision while storing an object", detail=digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return digest

    def put_json(self, obj) -> str:
        return self.put(canonical.dumpb(obj))

    def has(self, digest: str) -> bool:
        return self.path_for(digest).exists()

    def get(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if not path.exists():
            raise Integrity("object referenced by the chain is missing", detail=digest)
        data = path.read_bytes()
        if canonical.sha256_hex(data) != digest:
            raise Integrity("stored object does not hash to its own name", detail=digest)
        return data

    def get_json(self, digest: str):
        return canonical.loads(self.get(digest))

    def iter_objects(self):
        if not self.root.exists():
            return
        for shard in sorted(self.root.iterdir()):
            if not shard.is_dir():
                continue
            for path in sorted(shard.iterdir()):
                if path.is_file() and not path.name.endswith(".tmp"):
                    yield path
