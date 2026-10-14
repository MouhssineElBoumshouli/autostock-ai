"""Compute a deterministic SHA-256 digest for all files in an Odoo filestore tree."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def filestore_tree_sha256(root: Path) -> str:
    """Hash relative file names and file contents in deterministic order."""
    if not root.is_dir():
        raise ValueError(f"Filestore root does not exist or is not a directory: {root}")

    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(filestore_tree_sha256(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
