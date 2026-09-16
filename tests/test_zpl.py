"""Tests for the ZPL tokenizer, focused on the edge cases around the
line/column bookkeeping and the ^FD literal-scan that the rest of the
parser leans on."""

from __future__ import annotations

import unittest

from shipping_label_convert.zpl import Command, ZplError, _KNOWN_COMMANDS, tokenize


class TokenizeTests(unittest.TestCase):
    def test_empty_input_has_no_commands(self):
        self.assertEqual(tokenize(""), [])

    def test_whitespace_only_input_has_no_commands(self):
        self.assertEqual(tokenize("  \n\t\r\n  "), [])

    def test_character_outside_a_command_is_rejected(self):
        with self.assertRaises(ZplError) as ctx:
            tokenize("hello")
        self.assertEqual(ctx.exception.line, 1)
        self.assertEqual(ctx.exception.column, 1)
        self.assertIn("found 'h'", str(ctx.exception))

    def test_caret_with_no_command_letters_is_rejected(self):
        for bad in ("^", "^5", "^,"):
            with self.assertRaises(ZplError) as ctx:
                tokenize(bad)
            self.assertIn(
                "expected a one or two letter command name", str(ctx.exception)
            )

    def test_unknown_command_lists_known_commands(self):
        with self.assertRaises(ZplError) as ctx:
            tokenize("^ZZ")
        message = str(ctx.exception)
        self.assertIn("unknown command ^ZZ", message)
        self.assertIn(", ".join(sorted(_KNOWN_COMMANDS)), message)

    def test_one_letter_command_stops_at_first_digit(self):
        # ^A0N,30,30 is font "0", orientation N - the code is just "A",
        # everything else is arguments handled in convert.py.
        self.assertEqual(tokenize("^A0N,30,30"), [Command("A", "0N,30,30", 1, 1)])

    def test_two_letter_commands_are_recognized(self):
        commands = tokenize("^BY2^BCN,80")
        self.assertEqual(
            commands,
            [Command("BY", "2", 1, 1), Command("BC", "N,80", 1, 5)],
        )

    def test_field_data_runs_until_literal_fs(self):
        # A stray caret in the data that isn't followed by "FS" is just
        # more data, not the start of another command.
        commands = tokenize("^FDA^BX^FS")
        self.assertEqual(
            commands,
            [Command("FD", "A^BX", 1, 1), Command("FS", "", 1, 8)],
        )

    def test_unterminated_field_data_is_rejected(self):
        with self.assertRaises(ZplError) as ctx:
            tokenize("^FDhello")
        self.assertIn("never closed with ^FS", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)
        self.assertEqual(ctx.exception.column, 1)

    def test_command_args_stop_at_newline(self):
        commands = tokenize("^FO50,50\n^A0N,30,30")
        self.assertEqual(commands[0], Command("FO", "50,50", 1, 1))
        self.assertEqual(commands[1], Command("A", "0N,30,30", 2, 1))

    def test_error_position_accounts_for_earlier_lines(self):
        with self.assertRaises(ZplError) as ctx:
            tokenize("^XA\n^FO50,50\n?")
        self.assertEqual(ctx.exception.line, 3)
        self.assertEqual(ctx.exception.column, 1)


if __name__ == "__main__":
    unittest.main()
