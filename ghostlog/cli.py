"""Command line interface: `ghostlog summon`, `ghostlog lineage`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .lineage import build_lineage
from .logparse import read_remains
from .medium import DEFAULT_HOST, DEFAULT_MODEL, channel
from .tombstone import render

GREEN, GREY, BONE, GOLD, RESET = "\033[92m", "\033[90m", "\033[97m", "\033[33m", "\033[0m"


def _paint(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{RESET}" if enabled else text


def cmd_summon(args: argparse.Namespace) -> int:
    color = sys.stdout.isatty() and not args.no_color
    remains = read_remains(args.path)
    lineage = build_lineage(remains.sql_statements, dialect=args.dialect)
    seance = channel(remains, lineage, model=args.model, host=args.host, offline=args.offline)

    if seance.channeled:
        status = f"model: {args.model} (local, offline) ... connected to the other side"
    else:
        status = f"model: {seance.note} ... speaking through the offline template"
    print(_paint(f"  {status}", GREY, color))
    print()
    for i, line in enumerate(seance.testimony):
        prefix = "~ " if i == 0 else "   "
        print(_paint(prefix + line, BONE, color))
    print()
    print(_paint(f"  lineage: {lineage.describe()}", GOLD, color))
    if lineage.unparsed:
        print(_paint(f"  ({len(lineage.unparsed)} statement(s) could not be parsed)", GREY, color))
    out = Path(args.out)
    out.write_text(render(remains, lineage, seance), encoding="utf-8")
    print(_paint(f"  epitaph written -> {out}", GREY, color))
    return 0


def cmd_lineage(args: argparse.Namespace) -> int:
    remains = read_remains(args.path)
    lineage = build_lineage(remains.sql_statements, dialect=args.dialect)
    for src, tgt in lineage.edges:
        print(f"{src} -> {tgt}")
    if not lineage.edges:
        print("(no lineage found)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghostlog", description="A local seance for dead data pipelines."
    )
    parser.add_argument("--version", action="version", version=f"ghostlog {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    summon = sub.add_parser("summon", help="channel a dead job and write its tombstone")
    summon.add_argument("path", help="an old job log or a deprecated .sql file")
    summon.add_argument("--out", default="tombstone.html", help="tombstone HTML path")
    summon.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag")
    summon.add_argument("--host", default=DEFAULT_HOST, help="Ollama server URL")
    summon.add_argument("--dialect", default=None, help="sqlglot dialect, e.g. postgres")
    summon.add_argument("--offline", action="store_true", help="skip the model entirely")
    summon.add_argument("--no-color", action="store_true", help="plain output")
    summon.set_defaults(func=cmd_summon)

    lin = sub.add_parser("lineage", help="print table lineage edges only")
    lin.add_argument("path")
    lin.add_argument("--dialect", default=None)
    lin.set_defaults(func=cmd_lineage)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as err:
        print(f"ghostlog: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
