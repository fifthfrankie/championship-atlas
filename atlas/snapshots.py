"""Immutable gzip snapshots plus an append-only manifest. Same body = same id, so re-ingesting never duplicates."""
import gzip, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "snapshots"


def save(source, endpoint, params, body: bytes, status, fetched_at, root=None):
    root = root or ROOT
    sid = hashlib.sha256(body).hexdigest()
    rel = f"{source}/{sid[:2]}/{sid}.json.gz"
    path = root / rel
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(body, mtime=0))  # mtime=0 keeps the bytes reproducible
        tmp.replace(path)
    entry = dict(id=sid, source=source, endpoint=endpoint, params=params, fetched_at=fetched_at, http_status=status, path=rel)
    manifest = root / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def entries(root=None):
    root = root or ROOT
    manifest = root / "manifest.jsonl"
    if not manifest.exists():
        return []
    out = []
    lines = [l for l in manifest.read_text().splitlines() if l.strip()]
    for i, l in enumerate(lines):
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            if i != len(lines) - 1:   # only a torn final line (interrupted write) is forgiven
                raise
    return out


def read(entry, root=None):
    root = root or ROOT
    body = gzip.decompress((root / entry["path"]).read_bytes())
    if hashlib.sha256(body).hexdigest() != entry["id"]:
        raise ValueError(f"snapshot {entry['id']} fails its checksum")
    return body
