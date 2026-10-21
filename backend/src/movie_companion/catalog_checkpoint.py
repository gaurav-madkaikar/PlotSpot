"""Atomic, bounded import checkpoints; no credentials or conversation data."""
import json
import os
from pathlib import Path
import tempfile


def atomic_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-', suffix='.json')
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(payload, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_checkpoint(path: Path, *, max_bytes=45_000_000):
    if path.stat().st_size > max_bytes:
        raise ValueError('Checkpoint exceeds bound')
    return json.loads(path.read_text())
