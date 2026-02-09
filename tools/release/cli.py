from __future__ import annotations

import sys

from plain.cli import run_cli


def main() -> int:
    return run_cli(["release", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
