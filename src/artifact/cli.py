"""argparse dispatcher for ``artifact``.

The module is deliberately thin: it parses ``argv`` and calls into sibling
modules. No business logic lives here.

On import it sources a ``.env`` via ``python-dotenv`` (walking up from the
current working directory until the filesystem or a VCS root) so that
``GOOGLE_API_KEY`` and peers are available to the executor. Shell-exported
env vars still win (``override=False``) — this fills gaps without stomping
on CI/Docker-injected configuration.
"""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from dotenv import find_dotenv, load_dotenv

from artifact.exec import Executor

load_dotenv(find_dotenv(usecwd=True), override=False)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with its subcommands.

    Returns:
        A configured ``ArgumentParser`` ready to call ``parse_args``.
    """
    parser = argparse.ArgumentParser(prog="artifact", description="Run and manage artifacts.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Execute one artifact.")
    run.add_argument(
        "artifact_dir",
        help="Path to the artifact directory containing ARTIFACT.md.",
    )
    run.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Set a parameter. May be repeated.",
    )
    run.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Map an input name to a file path. May be repeated.",
    )
    run.add_argument(
        "--model",
        dest="model",
        default=None,
        metavar="PROVIDER:NAME",
        help="Override ARTIFACT.md's model for this run. Opaque to artifact.",
    )
    run.add_argument(
        "--promote-as",
        dest="promote_as",
        default=None,
        metavar="LABEL",
        help="Also promote the newly-created run under outs/<LABEL>/.",
    )

    promote = sub.add_parser("promote", help="Promote an existing run to a label.")
    promote.add_argument(
        "artifact_dir",
        help="Path to the artifact directory.",
    )
    promote.add_argument(
        "run_id",
        help="Basename of the run directory under runs/ to promote.",
    )
    promote.add_argument(
        "--as",
        dest="label",
        required=True,
        help="Label name to create under outs/.",
    )

    runs_cmd = sub.add_parser("runs", help="List runs in an artifact.")
    runs_cmd.add_argument(
        "artifact_dir",
        help="Path to the artifact directory.",
    )

    show_cmd = sub.add_parser("show", help="Show artifact frontmatter + labels.")
    show_cmd.add_argument(
        "artifact_dir",
        help="Path to the artifact directory.",
    )

    sub.add_parser(
        "template",
        help="Emit a reference ARTIFACT.md to stdout.",
        description=(
            "Print a reference ARTIFACT.md to stdout. Pipe to a file to scaffold "
            "by hand, or pipe directly into `artifact create <dir>` for the "
            "one-liner: artifact template | artifact create my-artifact"
        ),
    )

    create_cmd = sub.add_parser(
        "create",
        help="Read ARTIFACT.md from stdin and scaffold <dir>.",
        description=(
            "Read an ARTIFACT.md from stdin, validate it, and write it plus "
            "a runs/*-ignoring .gitignore into <dir>. stdin must be piped "
            "(not a TTY). Typical use: artifact template | artifact create <dir>"
        ),
    )
    create_cmd.add_argument(
        "dir",
        help="Destination directory. Will be created if absent; must be empty if present.",
    )

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


def main(
    argv: list[str] | None = None,
    *,
    executor: Executor | None = None,
    stdin: TextIO | None = None,
) -> int:
    """Entry point used by the console script.

    Args:
        argv: Argument list. ``None`` means read from ``sys.argv[1:]``.
        executor: Optional ``Executor`` for ``run``. ``None`` means the runner
            resolves one via ``get_executor(spec)`` based on ``spec.executor``.
            Public injection seam for tests.
        stdin: Optional stdin source for ``create``. ``None`` means
            ``sys.stdin``. Public injection seam for tests.

    Returns:
        The process exit code.
    """
    from artifact.promote import promote as promote_run
    from artifact.runner import run as run_artifact

    parser = build_parser()
    args = parser.parse_args(argv)
    stdin = stdin if stdin is not None else sys.stdin

    if args.cmd == "run":
        if args.model == "":
            print("error: --model requires a non-empty string", file=sys.stderr)
            return 1
        if args.model is not None and ":" in args.model:
            # Pre-validate against claude_cli artifacts. We need the executor
            # string, which requires parsing the spec. Failures here are
            # converted to the same ``error: ...`` surface the runner uses.
            from artifact.spec import SpecError, parse_spec
            from pathlib import Path as _P
            try:
                _spec = parse_spec(_P(args.artifact_dir) / "ARTIFACT.md")
            except (SpecError, OSError) as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            if _spec.executor == "claude_cli":
                print(
                    f"error: --model for executor: claude_cli requires a "
                    f"bare Claude model name (no provider prefix); got "
                    f"{args.model!r}",
                    file=sys.stderr,
                )
                return 1
        params = _split_kv(args.param, "--param")
        inputs = _split_kv(args.input, "--input")
        try:
            run_dir = run_artifact(
                args.artifact_dir,
                params=params,
                inputs=inputs,
                executor=executor,
                model=args.model,
            )
            if args.promote_as:
                promote_run(args.artifact_dir, run_dir.name, label=args.promote_as)
        except (ValueError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(run_dir)
        return 0

    if args.cmd == "promote":
        try:
            out_path = promote_run(args.artifact_dir, args.run_id, label=args.label)
        except (ValueError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(out_path)
        return 0

    if args.cmd == "runs":
        from artifact.introspect import list_runs

        for row in list_runs(args.artifact_dir):
            promoted = ",".join(row.promoted_to) or "-"
            params_s = " ".join(f"{k}={v}" for k, v in row.params.items()) or "-"
            print(f"{row.run_id}\t{row.timestamp}\t{promoted}\t{params_s}")
        return 0

    if args.cmd == "show":
        try:
            from artifact.introspect import show

            print(show(args.artifact_dir), end="")
        except (ValueError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "template":
        from artifact.create import render_template

        sys.stdout.write(render_template())
        return 0

    if args.cmd == "create":
        from pathlib import Path

        from artifact.create import create as create_artifact
        from artifact.spec import SpecError

        if stdin.isatty():
            print(
                "error: create reads ARTIFACT.md from stdin; "
                "try: artifact template | artifact create <dir>",
                file=sys.stderr,
            )
            return 1
        content = stdin.read()
        if not content:
            print("error: stdin is empty", file=sys.stderr)
            return 1

        try:
            out = create_artifact(Path(args.dir), content=content)
        except (SpecError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(out)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
