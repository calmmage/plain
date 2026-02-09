from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_src_path() -> None:
    root = Path(__file__).resolve().parents[3]
    src = root / "src"
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_bootstrap_src_path()

from plain.cli import run_cli


def main() -> int:
    return run_cli(["obsidian", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
