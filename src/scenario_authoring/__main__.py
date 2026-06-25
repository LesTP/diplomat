"""Unified `python -m scenario_authoring` dispatcher."""

from __future__ import annotations

import argparse
import sys
from typing import Callable

from scenario_authoring import (
    scenario_brief,
    scenario_builder,
    scenario_compiler,
    verify_scenario_optimum,
)

_COMMANDS: dict[str, Callable[[], int | None]] = {
    "build": scenario_builder.main,
    "compile": scenario_compiler.main,
    "verify": verify_scenario_optimum.main,
    "brief": scenario_brief.main,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scenario_authoring",
        description="Unified scenario_authoring CLI dispatcher.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Subcommand: build, compile, verify, or brief",
    )
    args, remaining = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        return 2

    handler = _COMMANDS.get(args.command)
    if handler is None:
        print(f"ERROR: unknown subcommand: {args.command}", file=sys.stderr)
        return 2

    old_argv = sys.argv
    sys.argv = [old_argv[0], *remaining]
    try:
        result = handler()
    finally:
        sys.argv = old_argv

    if isinstance(result, int):
        return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
