"""argparse dispatcher for ``artifact``.

The module is deliberately thin: it parses ``argv`` and calls into sibling
modules. No business logic lives here.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with its subcommands.

    Returns:
        A configured ``ArgumentParser`` ready to call ``parse_args``.
    """
    parser = argparse.ArgumentParser(prog="artifact", description="Run and manage artifacts.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Execute one artifact.")
    run.add_argument("artifact_dir")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point used by the console script.

    Args:
        argv: Argument list. ``None`` means read from ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "run":
        print(f"run {args.artifact_dir}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
