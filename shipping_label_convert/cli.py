"""Command line entry point: zpl <-> json."""

from __future__ import annotations

import argparse
import json
import sys

from .convert import LabelError, label_to_zpl, labels_to_zpl, zpl_to_labels
from .preview import (
    DEFAULT_DOTS_PER_COL,
    DEFAULT_DOTS_PER_ROW,
    render_preview,
    render_previews,
)
from .zpl import ZplError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="shipping-label-convert",
        description="Convert shipping labels between ZPL and JSON.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    to_json = subparsers.add_parser("to-json", help="convert a ZPL file to JSON")
    to_json.add_argument("input", help="path to a .zpl file, or - for stdin")

    to_zpl = subparsers.add_parser("to-zpl", help="convert a JSON file to ZPL")
    to_zpl.add_argument("input", help="path to a .json file, or - for stdin")

    preview = subparsers.add_parser("preview", help="draw a ZPL file as ascii art")
    preview.add_argument("input", help="path to a .zpl file, or - for stdin")
    preview.add_argument(
        "--dots-per-col",
        type=int,
        default=DEFAULT_DOTS_PER_COL,
        help="printer dots per character column (default: %(default)s)",
    )
    preview.add_argument(
        "--dots-per-row",
        type=int,
        default=DEFAULT_DOTS_PER_ROW,
        help="printer dots per character row (default: %(default)s)",
    )

    args = parser.parse_args(argv)
    if args.command == "preview" and (args.dots_per_col < 1 or args.dots_per_row < 1):
        parser.error("--dots-per-col and --dots-per-row must be at least 1")
    text = sys.stdin.read() if args.input == "-" else _read_file(args.input)

    if args.command == "preview":
        try:
            labels = zpl_to_labels(text)
        except ZplError as error:
            print(f"{args.input}:{error}", file=sys.stderr)
            return 1
        sizes = {"dots_per_col": args.dots_per_col, "dots_per_row": args.dots_per_row}
        if len(labels) == 1:
            sys.stdout.write(render_preview(labels[0], **sizes))
        else:
            sys.stdout.write(render_previews(labels, **sizes))
        return 0

    if args.command == "to-json":
        try:
            labels = zpl_to_labels(text)
        except ZplError as error:
            print(f"{args.input}:{error}", file=sys.stderr)
            return 1
        # A file with one label round-trips as a single JSON object; a
        # batch of labels round-trips as a JSON array of that same shape.
        json.dump(labels[0] if len(labels) == 1 else labels, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    parsed = json.loads(text)
    try:
        if isinstance(parsed, list):
            zpl_text = labels_to_zpl(parsed)
        else:
            zpl_text = label_to_zpl(parsed)
    except LabelError as error:
        print(f"{args.input}:{error}", file=sys.stderr)
        return 1
    sys.stdout.write(zpl_text)
    return 0


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


if __name__ == "__main__":
    sys.exit(main())
