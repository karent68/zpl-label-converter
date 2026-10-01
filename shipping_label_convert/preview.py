"""Draw a label dict as ascii art so you can check a layout without a printer.

One character cell stands for a block of printer dots. Cells are taller
than they are wide, so the default is twice as many dots per row as per
column, which keeps boxes roughly square on screen.

This is a layout check, not a renderer: text is drawn left to right at
its starting position whatever its font size or orientation, and barcode
bars are a stand-in pattern derived from the data (the real Code 128
encoding is not computed). Positions and sizes are what you can trust.
"""

from __future__ import annotations

import math

DEFAULT_DOTS_PER_COL = 8
DEFAULT_DOTS_PER_ROW = 16

# ZPL's own default when a label has no ^BY.
_DEFAULT_MODULE_WIDTH = 2


def render_preview(
    label: dict,
    dots_per_col: int = DEFAULT_DOTS_PER_COL,
    dots_per_row: int = DEFAULT_DOTS_PER_ROW,
) -> str:
    if dots_per_col < 1 or dots_per_row < 1:
        raise ValueError("dots per column and per row must be at least 1")

    module_width = label.get("module_width", _DEFAULT_MODULE_WIDTH)
    cells = {}

    def put(col: int, row: int, char: str) -> None:
        cells[(col, row)] = char

    for field in label.get("fields", []):
        col = field["x"] // dots_per_col
        row = field["y"] // dots_per_row
        kind = field.get("type", "text")
        if kind == "box":
            if field.get("color", "B") == "B":
                _draw_box(put, col, row, field, dots_per_col, dots_per_row)
        elif kind == "barcode":
            _draw_barcode(put, col, row, field, module_width, dots_per_col, dots_per_row)
        else:
            for offset, char in enumerate(field.get("data", "")):
                put(col + offset, row, char)

    if not cells:
        return ""

    width = max(col for col, _ in cells) + 1
    height = max(row for _, row in cells) + 1
    lines = []
    for row in range(height):
        line = "".join(cells.get((col, row), " ") for col in range(width))
        lines.append(line.rstrip())
    return "\n".join(lines) + "\n"


def render_previews(labels: list, **kwargs) -> str:
    """Preview several labels, each under a header so the breaks are obvious."""
    parts = []
    for index, label in enumerate(labels):
        parts.append(f"--- label {index + 1} of {len(labels)} ---\n")
        parts.append(render_preview(label, **kwargs))
    return "".join(parts)


def _draw_box(put, col: int, row: int, field: dict, dots_per_col: int, dots_per_row: int) -> None:
    cols = max(1, round(field["width"] / dots_per_col))
    rows = max(1, round(field["height"] / dots_per_row))
    # A box thinner than one cell in either direction is a rule line, which
    # is how shipping labels use ^GB for dividers.
    if rows == 1:
        for offset in range(cols):
            put(col + offset, row, "-")
        return
    if cols == 1:
        for offset in range(rows):
            put(col, row + offset, "|")
        return
    for offset in range(cols):
        put(col + offset, row, "-")
        put(col + offset, row + rows - 1, "-")
    for offset in range(rows):
        put(col, row + offset, "|")
        put(col + cols - 1, row + offset, "|")
    for corner_col in (col, col + cols - 1):
        for corner_row in (row, row + rows - 1):
            put(corner_col, corner_row, "+")


def _draw_barcode(
    put, col: int, row: int, field: dict, module_width: int, dots_per_col: int, dots_per_row: int
) -> None:
    data = field.get("data", "")
    # Code 128 spends 11 modules per symbol, plus start, check and a
    # 13-module stop pattern.
    modules = 11 * (len(data) + 2) + 13
    cols = max(1, math.ceil(modules * module_width / dots_per_col))
    rows = max(1, round(field.get("height", 100) / dots_per_row))
    bits = _bit_pattern(data, cols)
    for offset, bit in enumerate(bits):
        if not bit:
            continue
        for down in range(rows):
            put(col + offset, row + down, "|")


def _bit_pattern(data: str, length: int) -> list:
    # Deterministic so the same data always previews the same way. The
    # first and last cells are always bars so the code has visible edges.
    state = 5381
    for char in data:
        state = (state * 33 + ord(char)) & 0xFFFFFFFF
    bits = []
    for _ in range(length):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        bits.append((state >> 16) & 1 == 1)
    bits[0] = True
    bits[-1] = True
    return bits
