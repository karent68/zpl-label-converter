"""Tests for the ZPL <-> dict conversion, focused on the structural
edge cases: unbalanced ^XA/^XZ, fields opened or closed out of order,
and the places a command needs a number it didn't get."""

from __future__ import annotations

import unittest

from shipping_label_convert.convert import (
    label_to_zpl,
    labels_to_zpl,
    zpl_to_label,
    zpl_to_labels,
)
from shipping_label_convert.zpl import ZplError

SAMPLE_ZPL = """^XA
^FO50,50
^A0N,30,30
^FDSHIP TO: Jane Doe^FS
^FO50,100
^BY2
^BCN,80
^FD1Z999AA10123456784^FS
^XZ
"""


class ZplToLabelTests(unittest.TestCase):
    def test_parses_text_and_barcode_fields(self):
        label = zpl_to_label(SAMPLE_ZPL)
        self.assertEqual(
            label,
            {
                "module_width": 2,
                "fields": [
                    {
                        "x": 50,
                        "y": 50,
                        "font": "0",
                        "orientation": "N",
                        "height": 30,
                        "width": 30,
                        "type": "text",
                        "data": "SHIP TO: Jane Doe",
                    },
                    {
                        "x": 50,
                        "y": 100,
                        "type": "barcode",
                        "symbology": "code128",
                        "orientation": "N",
                        "height": 80,
                        "data": "1Z999AA10123456784",
                    },
                ],
            },
        )

    def test_default_font_fills_in_fields_that_omit_one(self):
        label = zpl_to_label("^XA^CF0,20,20^FO10,10^FDHello^FS^XZ")
        self.assertEqual(
            label,
            {
                "default_font": {"font": "0", "height": 20, "width": 20},
                "fields": [
                    {
                        "x": 10,
                        "y": 10,
                        "type": "text",
                        "data": "Hello",
                        "font": "0",
                        "height": 20,
                        "width": 20,
                    }
                ],
            },
        )

    def test_default_font_does_not_leak_into_box_fields(self):
        label = zpl_to_label("^XA^CF0,20,20^FO10,10^GB50,50,2^FS^XZ")
        self.assertNotIn("font", label["fields"][0])

    def test_no_label_in_file_is_an_error(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("")
        self.assertIn("no ^XA...^XZ label found", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)
        self.assertEqual(ctx.exception.column, 1)

    def test_command_before_xa_is_an_error(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^FO10,10^FS")
        self.assertIn("expected ^XA to start a label", str(ctx.exception))
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 1))

    def test_nested_xa_is_an_error(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^XA^XZ^XZ")
        self.assertIn("^XA found inside a label", str(ctx.exception))
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 4))

    def test_unclosed_label_points_at_the_last_command(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FO10,10^FS")
        self.assertIn("label was never closed with ^XZ", str(ctx.exception))
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 12))

    def test_unclosed_field_points_at_the_fo_that_opened_it(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FO10,10^XZ")
        self.assertIn("was never closed with ^FS", str(ctx.exception))
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 4))

    def test_fs_without_fo_is_an_error(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FS^XZ")
        self.assertIn("no field was started with ^FO", str(ctx.exception))
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 4))

    def test_fo_needs_both_coordinates(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FO50^FS^XZ")
        self.assertIn("^FO needs an x and y position", str(ctx.exception))
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 4))

    def test_fo_position_must_be_a_number(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FOabc,50^FS^XZ")
        self.assertIn(
            "expected a whole number for x position in ^FO, found 'abc'",
            str(ctx.exception),
        )

    def test_font_before_fo_is_an_error(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^A0N,30,30^FS^XZ")
        self.assertIn("must come after a ^FO", str(ctx.exception))

    def test_gb_needs_width_and_height(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FO10,10^GB^FS^XZ")
        self.assertIn("^GB needs a width and height", str(ctx.exception))

    def test_gb_color_must_be_b_or_w(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^FO10,10^GB200,200,5,X^FS^XZ")
        self.assertIn(
            "expected B or W for box color in ^GB, found 'X'", str(ctx.exception)
        )

    def test_cf_needs_a_font(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label("^XA^CF^XZ")
        self.assertIn("^CF needs a font", str(ctx.exception))


class MultipleLabelTests(unittest.TestCase):
    TWO_LABELS = "^XA^FO0,0^FDA^FS^XZ^XA^FO0,0^FDB^FS^XZ"

    def test_zpl_to_labels_returns_one_dict_per_block(self):
        labels = zpl_to_labels(self.TWO_LABELS)
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0]["fields"][0]["data"], "A")
        self.assertEqual(labels[1]["fields"][0]["data"], "B")

    def test_zpl_to_label_rejects_a_file_with_more_than_one_label(self):
        with self.assertRaises(ZplError) as ctx:
            zpl_to_label(self.TWO_LABELS)
        self.assertIn("found 2 labels", str(ctx.exception))
        self.assertIn("zpl_to_labels", str(ctx.exception))
        # Points at the second ^XA, not the first.
        self.assertEqual((ctx.exception.line, ctx.exception.column), (1, 20))

    def test_labels_to_zpl_round_trips_a_batch(self):
        labels = zpl_to_labels(self.TWO_LABELS)
        self.assertEqual(zpl_to_labels(labels_to_zpl(labels)), labels)


class LabelToZplTests(unittest.TestCase):
    def test_round_trips_the_sample_label(self):
        label = zpl_to_label(SAMPLE_ZPL)
        regenerated = label_to_zpl(label)
        self.assertEqual(zpl_to_label(regenerated), label)

    def test_missing_position_is_an_error(self):
        with self.assertRaises(ValueError) as ctx:
            label_to_zpl({"fields": [{"data": "hi"}]})
        self.assertIn("field 0 is missing an x/y position", str(ctx.exception))

    def test_missing_data_is_an_error(self):
        with self.assertRaises(ValueError) as ctx:
            label_to_zpl({"fields": [{"x": 1, "y": 1}]})
        self.assertIn("field 0 is missing its text data", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
