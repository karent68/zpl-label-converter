"""Convert between ZPL command streams and a plain, JSON-friendly dict.

The dict shape is intentionally small:

    {
        "module_width": 2,
        "fields": [
            {"type": "text", "x": 50, "y": 50, "font": "0",
             "orientation": "N", "height": 30, "width": 30,
             "data": "SHIP TO: Jane Doe"},
            {"type": "barcode", "x": 50, "y": 100, "orientation": "N",
             "height": 80, "symbology": "code128",
             "data": "1Z999AA10123456784"},
        ],
    }

A ZPL file may hold more than one ^XA...^XZ block (a batch of labels
printed together); zpl_to_labels/labels_to_zpl handle that case as a
list of the dict above, while zpl_to_label/label_to_zpl handle the
common single-label file.
"""

from __future__ import annotations

from .zpl import Command, ZplError, tokenize


def zpl_to_label(text: str) -> dict:
    """Parse a ZPL file that holds exactly one ^XA...^XZ label."""
    labels = _parse_all_labels(text)
    if len(labels) > 1:
        _, second_start = labels[1]
        raise ZplError(
            f"found {len(labels)} labels in this file; use zpl_to_labels for "
            "files with more than one ^XA...^XZ block",
            second_start.line,
            second_start.column,
        )
    return labels[0][0]


def zpl_to_labels(text: str) -> list:
    """Parse a ZPL file that may hold one or more ^XA...^XZ labels."""
    return [label for label, _ in _parse_all_labels(text)]


def _parse_all_labels(text: str) -> list:
    commands = tokenize(text)
    results = []
    label: dict | None = None
    label_start: Command | None = None
    current: dict | None = None
    field_start: Command | None = None

    for command in commands:
        if command.name == "XA":
            if label is not None:
                raise ZplError(
                    "^XA found inside a label; close it with ^XZ before "
                    "starting the next one",
                    command.line,
                    command.column,
                )
            label = {"fields": []}
            label_start = command
            continue

        if label is None:
            raise ZplError(
                "expected ^XA to start a label",
                command.line,
                command.column,
            )

        if command.name == "XZ":
            if current is not None:
                raise ZplError(
                    f"field at ({current.get('x')}, {current.get('y')}) "
                    "was never closed with ^FS",
                    field_start.line,
                    field_start.column,
                )
            results.append((label, label_start))
            label = None
            label_start = None
            continue

        if command.name == "FO":
            parts = command.args.split(",")
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ZplError(
                    "^FO needs an x and y position, e.g. ^FO50,50",
                    command.line,
                    command.column,
                )
            current = {
                "x": _parse_int(command, parts[0], "x position"),
                "y": _parse_int(command, parts[1], "y position"),
            }
            field_start = command
            continue

        if command.name == "A":
            _require_open_field(command, current, "^A (font)")
            parts = command.args.split(",")
            head = parts[0]
            current["font"] = head[:1] or "0"
            current["orientation"] = head[1:2] or "N"
            if len(parts) >= 2 and parts[1]:
                current["height"] = _parse_int(command, parts[1], "font height")
            if len(parts) >= 3 and parts[2]:
                current["width"] = _parse_int(command, parts[2], "font width")
            continue

        if command.name == "BC":
            _require_open_field(command, current, "^BC (barcode)")
            parts = command.args.split(",")
            current["type"] = "barcode"
            current["symbology"] = "code128"
            current["orientation"] = parts[0][:1] or "N"
            if len(parts) >= 2 and parts[1]:
                current["height"] = _parse_int(command, parts[1], "barcode height")
            continue

        if command.name == "BY":
            parts = command.args.split(",")
            if parts and parts[0]:
                label["module_width"] = _parse_int(command, parts[0], "module width")
            continue

        if command.name == "GB":
            _require_open_field(command, current, "^GB (graphic box)")
            parts = command.args.split(",")
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ZplError(
                    "^GB needs a width and height, e.g. ^GB200,200,5",
                    command.line,
                    command.column,
                )
            current["type"] = "box"
            current["width"] = _parse_int(command, parts[0], "box width")
            current["height"] = _parse_int(command, parts[1], "box height")
            current["thickness"] = (
                _parse_int(command, parts[2], "box border thickness")
                if len(parts) >= 3 and parts[2]
                else 1
            )
            if len(parts) >= 4 and parts[3]:
                if parts[3] not in ("B", "W"):
                    raise ZplError(
                        f"expected B or W for box color in ^GB, found {parts[3]!r}",
                        command.line,
                        command.column,
                    )
                current["color"] = parts[3]
            if len(parts) >= 5 and parts[4]:
                current["rounding"] = _parse_int(command, parts[4], "box corner rounding")
            continue

        if command.name == "CF":
            parts = command.args.split(",")
            if not parts or not parts[0]:
                raise ZplError(
                    "^CF needs a font, e.g. ^CF0,30,30",
                    command.line,
                    command.column,
                )
            default_font = {"font": parts[0][:1]}
            if len(parts) >= 2 and parts[1]:
                default_font["height"] = _parse_int(command, parts[1], "default font height")
            if len(parts) >= 3 and parts[2]:
                default_font["width"] = _parse_int(command, parts[2], "default font width")
            label["default_font"] = default_font
            continue

        if command.name == "FD":
            _require_open_field(command, current, "^FD (field data)")
            current.setdefault("type", "text")
            current["data"] = command.args
            continue

        if command.name == "FS":
            if current is None:
                raise ZplError(
                    "^FS closes a field, but no field was started with ^FO",
                    command.line,
                    command.column,
                )
            if current.get("type", "text") == "text":
                for key, value in label.get("default_font", {}).items():
                    current.setdefault(key, value)
            label["fields"].append(current)
            current = None
            continue

        if command.name == "FX":
            continue  # comment, no visible effect

    if label is not None:
        last = commands[-1]
        raise ZplError("label was never closed with ^XZ", last.line, last.column)

    if not results:
        raise ZplError("no ^XA...^XZ label found", 1, 1)

    return results


def _require_open_field(command: Command, current, what: str) -> None:
    if current is None:
        raise ZplError(
            f"{what} must come after a ^FO that positions the field",
            command.line,
            command.column,
        )


def _parse_int(command: Command, raw: str, what: str) -> int:
    try:
        return int(raw)
    except ValueError:
        raise ZplError(
            f"expected a whole number for {what} in ^{command.name}, found {raw!r}",
            command.line,
            command.column,
        ) from None


class LabelError(ValueError):
    """A label-to-ZPL conversion error with a JSON path a human can jump
    straight to, e.g. "fields[1].x: expected a whole number, found 'fifty'".
    """

    def __init__(self, reason: str, path: str):
        self.reason = reason
        self.path = path
        super().__init__(f"{path}: {reason}")


_VALID_FIELD_TYPES = {"text", "barcode", "box"}
_VALID_ORIENTATIONS = {"N", "R", "I", "B"}
_VALID_BOX_COLORS = {"B", "W"}


def _require_int(value, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LabelError(f"expected a whole number, found {value!r}", path)
    return value


def _require_str(value, path: str) -> str:
    if not isinstance(value, str):
        raise LabelError(f"expected a string, found {value!r}", path)
    return value


def _require_orientation(value, path: str) -> str:
    if value not in _VALID_ORIENTATIONS:
        raise LabelError(
            "expected one of N, R, I, B for orientation, found "
            f"{value!r}",
            path,
        )
    return value


def _render_default_font(default_font: dict) -> str:
    path = "default_font"
    if "font" not in default_font:
        raise LabelError("missing a font", f"{path}.font")
    parts = [_require_str(default_font["font"], f"{path}.font")]
    if "height" in default_font:
        parts.append(str(_require_int(default_font["height"], f"{path}.height")))
        if "width" in default_font:
            parts.append(str(_require_int(default_font["width"], f"{path}.width")))
    return f"^CF{','.join(parts)}"


def _render_box(field: dict, path: str) -> str:
    if "width" not in field:
        raise LabelError("box is missing a width", f"{path}.width")
    if "height" not in field:
        raise LabelError("box is missing a height", f"{path}.height")
    parts = [
        str(_require_int(field["width"], f"{path}.width")),
        str(_require_int(field["height"], f"{path}.height")),
        str(_require_int(field.get("thickness", 1), f"{path}.thickness")),
    ]
    if "color" in field or "rounding" in field:
        color = field.get("color", "B")
        if color not in _VALID_BOX_COLORS:
            raise LabelError(
                f"expected B or W for box color, found {color!r}", f"{path}.color"
            )
        parts.append(color)
    if "rounding" in field:
        parts.append(str(_require_int(field["rounding"], f"{path}.rounding")))
    return f"^GB{','.join(parts)}"


def _render_barcode(field: dict, path: str) -> str:
    symbology = field.get("symbology", "code128")
    if symbology != "code128":
        raise LabelError(
            f"unsupported barcode symbology {symbology!r} "
            "(only 'code128' is supported)",
            f"{path}.symbology",
        )
    orientation = _require_orientation(field.get("orientation", "N"), f"{path}.orientation")
    height = _require_int(field.get("height", 100), f"{path}.height")
    return f"^BC{orientation},{height}"


def _render_text_font(field: dict, path: str):
    font = _require_str(field.get("font", "0"), f"{path}.font")
    orientation = _require_orientation(field.get("orientation", "N"), f"{path}.orientation")
    height = field.get("height")
    width = field.get("width")
    if width is not None and height is None:
        raise LabelError("width given without a height", f"{path}.height")
    if height is None:
        return None
    height = _require_int(height, f"{path}.height")
    if width is not None:
        width = _require_int(width, f"{path}.width")
        return f"^A{font}{orientation},{height},{width}"
    return f"^A{font}{orientation},{height}"


def _render_field(field, path: str) -> list:
    if not isinstance(field, dict):
        raise LabelError(f"expected an object, found {field!r}", path)

    if "x" not in field:
        raise LabelError("missing x position", f"{path}.x")
    if "y" not in field:
        raise LabelError("missing y position", f"{path}.y")
    x = _require_int(field["x"], f"{path}.x")
    y = _require_int(field["y"], f"{path}.y")

    field_type = field.get("type", "text")
    if field_type not in _VALID_FIELD_TYPES:
        raise LabelError(
            f"unknown field type {field_type!r} (expected one of "
            + ", ".join(sorted(_VALID_FIELD_TYPES))
            + ")",
            f"{path}.type",
        )

    lines = [f"^FO{x},{y}"]

    if field_type == "box":
        lines.append(_render_box(field, path))
        lines.append("^FS")
        return lines

    if field_type == "barcode":
        lines.append(_render_barcode(field, path))
    else:
        font_command = _render_text_font(field, path)
        if font_command is not None:
            lines.append(font_command)

    if "data" not in field:
        raise LabelError("missing text data", f"{path}.data")
    data = _require_str(field["data"], f"{path}.data")
    lines.append(f"^FD{data}^FS")
    return lines


def label_to_zpl(label: dict) -> str:
    if not isinstance(label, dict):
        raise LabelError(f"expected an object, found {label!r}", "$")

    lines = ["^XA"]

    if "module_width" in label:
        lines.append(f"^BY{_require_int(label['module_width'], 'module_width')}")

    default_font = label.get("default_font")
    if default_font:
        lines.append(_render_default_font(default_font))

    fields = label.get("fields", [])
    if not isinstance(fields, list):
        raise LabelError(f"expected an array, found {fields!r}", "fields")

    for index, field in enumerate(fields):
        lines.extend(_render_field(field, f"fields[{index}]"))

    lines.append("^XZ")
    return "\n".join(lines) + "\n"


def labels_to_zpl(labels: list) -> str:
    """Render a batch of labels as one ZPL file, one ^XA...^XZ block per label."""
    chunks = []
    for index, label in enumerate(labels):
        try:
            chunks.append(label_to_zpl(label))
        except LabelError as error:
            prefix = f"labels[{index}]"
            path = prefix if error.path == "$" else f"{prefix}.{error.path}"
            raise LabelError(error.reason, path) from None
    return "".join(chunks)
