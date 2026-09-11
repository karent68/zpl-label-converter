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
"""

from __future__ import annotations

from .zpl import Command, ZplError, tokenize


def zpl_to_label(text: str) -> dict:
    commands = tokenize(text)
    if not commands or commands[0].name != "XA":
        line, column = (commands[0].line, commands[0].column) if commands else (1, 1)
        raise ZplError("a label must start with ^XA", line, column)

    label: dict = {"fields": []}
    current: dict | None = None
    closed = False

    for command in commands[1:]:
        if command.name == "XA":
            raise ZplError(
                "^XA found inside a label; only one label per document is supported",
                command.line,
                command.column,
            )

        if command.name == "XZ":
            closed = True
            break

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

    if not closed:
        last = commands[-1]
        raise ZplError("label was never closed with ^XZ", last.line, last.column)

    if current is not None:
        raise ZplError(
            f"field at ({current.get('x')}, {current.get('y')}) was never closed with ^FS",
            commands[0].line,
            commands[0].column,
        )

    return label


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


def label_to_zpl(label: dict) -> str:
    lines = ["^XA"]

    module_width = label.get("module_width")
    if module_width is not None:
        lines.append(f"^BY{module_width}")

    default_font = label.get("default_font")
    if default_font:
        parts = [default_font.get("font", "0")]
        if "height" in default_font:
            parts.append(str(default_font["height"]))
            if "width" in default_font:
                parts.append(str(default_font["width"]))
        lines.append(f"^CF{','.join(parts)}")

    for index, field in enumerate(label.get("fields", [])):
        if "x" not in field or "y" not in field:
            raise ValueError(f"field {index} is missing an x/y position")
        lines.append(f"^FO{field['x']},{field['y']}")

        field_type = field.get("type")
        if field_type == "barcode":
            orientation = field.get("orientation", "N")
            height = field.get("height", 100)
            lines.append(f"^BC{orientation},{height}")
        elif field_type == "box":
            parts = [
                str(field.get("width", 1)),
                str(field.get("height", 1)),
                str(field.get("thickness", 1)),
            ]
            if "color" in field or "rounding" in field:
                parts.append(field.get("color", "B"))
            if "rounding" in field:
                parts.append(str(field["rounding"]))
            lines.append(f"^GB{','.join(parts)}")
            lines.append("^FS")
            continue
        else:
            font = field.get("font", "0")
            orientation = field.get("orientation", "N")
            height = field.get("height")
            width = field.get("width")
            if height is not None and width is not None:
                lines.append(f"^A{font}{orientation},{height},{width}")
            elif height is not None:
                lines.append(f"^A{font}{orientation},{height}")

        if "data" not in field:
            raise ValueError(f"field {index} is missing its text data")
        lines.append(f"^FD{field['data']}^FS")

    lines.append("^XZ")
    return "\n".join(lines) + "\n"
