"""Command line entry point: zpl <-> json."""

from __future__ import annotations

import argparse
import json
import sys

from .convert import label_to_zpl, labels_to_zpl, zpl_to_labels
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

    args = parser.parse_args(argv)
    text = sys.stdin.read() if args.input == "-" else _read_file(args.input)

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
    if isinstance(parsed, list):
        sys.stdout.write(labels_to_zpl(parsed))
    else:
        sys.stdout.write(label_to_zpl(parsed))
    return 0


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


if __name__ == "__main__":
    sys.exit(main())
