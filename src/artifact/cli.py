"""argparse dispatcher for ``artifact``.

The module is deliberately thin: it parses ``argv`` and calls into sibling
modules. No business logic lives here.
"""

from __future__ import annotations

import argparse
import sys

from artifact.exec import Executor, deepagent_executor


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with its subcommands.

    Returns:
        A configured ``ArgumentParser`` ready to call ``parse_args``.
    """
    parser = argparse.ArgumentParser(prog="artifact", description="Run and manage artifacts.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Execute one artifact.")
    run.add_argument("artifact_dir")
    run.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    run.add_argument("--input", action="append", default=[], metavar="NAME=PATH")
    run.add_argument("--promote-as", dest="promote_as", default=None, metavar="LABEL")

    promote = sub.add_parser("promote", help="Promote an existing run to a label.")
    promote.add_argument("artifact_dir")
    promote.add_argument("run_id")
    promote.add_argument("--as", dest="label", required=True)

    return parser


def _split_kv(items: list[str], flag: str) -> dict[str, str]:
    """Parse a list of ``NAME=VALUE`` strings into a dict; raise ``SystemExit`` on malformed."""
    out: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise SystemExit(f"{flag} expects NAME=VALUE, got {raw!r}")
        name, _, value = raw.partition("=")
        if not name:
            raise SystemExit(f"{flag} expects NAME=VALUE, got {raw!r}")
        out[name] = value
    return out


def main(argv: list[str] | None = None, *, executor: Executor | None = None) -> int:
    """Entry point used by the console script.

    Args:
        argv: Argument list. ``None`` means read from ``sys.argv[1:]``.
        executor: Optional ``Executor`` for ``run``. Defaults to
            ``deepagent_executor`` (real LLM). Public injection seam for tests.

    Returns:
        The process exit code.
    """
    from artifact.promote import PromoteError, promote as promote_run
    from artifact.runner import RunnerError, run as run_artifact

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        params = _split_kv(args.param, "--param")
        inputs = _split_kv(args.input, "--input")
        try:
            run_dir = run_artifact(
                args.artifact_dir,
                params=params,
                inputs=inputs,
                executor=executor or deepagent_executor,
            )
            if args.promote_as:
                promote_run(args.artifact_dir, run_dir.name, label=args.promote_as)
        except (RunnerError, PromoteError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(run_dir)
        return 0

    if args.cmd == "promote":
        try:
            out_path = promote_run(args.artifact_dir, args.run_id, label=args.label)
        except PromoteError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(out_path)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
