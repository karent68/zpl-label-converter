"""Tokenizer for ZPL (Zebra Programming Language) label markup.

ZPL has no single published grammar, so this follows the command
reference: a label is `^XA ... ^XZ`, and each command is a caret
(format) or tilde (control) prefix, a one or two letter code, and then
a run of characters up to the next command or the end of input. What
those characters mean is up to the command itself - `^FO50,50` and
`^A0N,30,30` split their arguments differently, so that splitting
happens in convert.py, not here.
"""

from __future__ import annotations

from dataclasses import dataclass


class ZplError(Exception):
    """A parse error with a location a human can jump straight to."""

    def __init__(self, message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(f"line {line}, column {column}: {message}")


@dataclass
class Command:
    name: str  # e.g. "FO", "XA", "FD"
    args: str  # raw text after the command code; the field data for ^FD
    line: int
    column: int


_KNOWN_COMMANDS = {"XA", "XZ", "FO", "FD", "FS", "FX", "A", "BY", "BC"}


class _Scanner:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1

    def at_end(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return "" if self.at_end() else self.text[self.pos]

    def advance(self) -> str:
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch


def tokenize(text: str) -> list:
    scanner = _Scanner(text)
    commands = []

    while not scanner.at_end():
        ch = scanner.peek()
        if ch in " \t\r\n":
            scanner.advance()
            continue

        if ch not in "^~":
            raise ZplError(
                f"expected a command starting with ^ or ~, found {ch!r}",
                scanner.line,
                scanner.column,
            )

        start_line, start_column = scanner.line, scanner.column
        scanner.advance()  # consume ^ or ~

        code_chars = []
        while not scanner.at_end() and scanner.peek().isalpha() and len(code_chars) < 2:
            code_chars.append(scanner.advance())
        name = "".join(code_chars)

        if not name:
            raise ZplError(
                "expected a one or two letter command name after ^",
                start_line,
                start_column,
            )
        if name not in _KNOWN_COMMANDS:
            raise ZplError(
                f"unknown command ^{name} (known commands: "
                + ", ".join(sorted(_KNOWN_COMMANDS))
                + ")",
                start_line,
                start_column,
            )

        if name == "FD":
            # Field data runs until the literal ^FS, not until the next
            # command, since the data itself may contain odd characters.
            data_chars = []
            while True:
                if scanner.at_end():
                    raise ZplError(
                        "^FD field data was never closed with ^FS",
                        start_line,
                        start_column,
                    )
                if scanner.text.startswith("^FS", scanner.pos):
                    break
                data_chars.append(scanner.advance())
            commands.append(Command(name, "".join(data_chars), start_line, start_column))
            continue

        arg_chars = []
        while not scanner.at_end() and scanner.peek() not in "^~\r\n":
            arg_chars.append(scanner.advance())
        commands.append(Command(name, "".join(arg_chars), start_line, start_column))

    return commands
