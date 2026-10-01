"""Tests for the ascii-art label preview."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest

from shipping_label_convert.cli import main
from shipping_label_convert.preview import render_preview, render_previews


class RenderPreviewTests(unittest.TestCase):
    def test_empty_label_renders_nothing(self):
        self.assertEqual(render_preview({"fields": []}), "")

    def test_text_lands_at_scaled_position(self):
        label = {"fields": [{"type": "text", "x": 16, "y": 32, "data": "AB"}]}
        self.assertEqual(render_preview(label), "\n\n  AB\n")

    def test_dots_per_cell_can_be_changed(self):
        label = {"fields": [{"type": "text", "x": 4, "y": 4, "data": "A"}]}
        self.assertEqual(
            render_preview(label, dots_per_col=2, dots_per_row=2), "\n\n  A\n"
        )

    def test_box_outline(self):
        label = {"fields": [{"type": "box", "x": 0, "y": 0, "width": 32, "height": 48}]}
        self.assertEqual(render_preview(label), "+--+\n|  |\n+--+\n")

    def test_flat_box_is_a_rule_line(self):
        label = {"fields": [{"type": "box", "x": 0, "y": 0, "width": 80, "height": 2}]}
        self.assertEqual(render_preview(label), "-" * 10 + "\n")

    def test_narrow_box_is_a_vertical_line(self):
        label = {"fields": [{"type": "box", "x": 0, "y": 0, "width": 2, "height": 48}]}
        self.assertEqual(render_preview(label), "|\n|\n|\n")

    def test_white_box_draws_nothing(self):
        label = {
            "fields": [
                {"type": "box", "x": 0, "y": 0, "width": 32, "height": 48, "color": "W"}
            ]
        }
        self.assertEqual(render_preview(label), "")

    def test_barcode_size_and_edges(self):
        label = {
            "module_width": 2,
            "fields": [
                {"type": "barcode", "x": 0, "y": 0, "height": 32, "data": "A"}
            ],
        }
        lines = render_preview(label).splitlines()
        # 46 modules at 2 dots each, 8 dots per column, rounded up.
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], lines[1])
        self.assertEqual(len(lines[0]), 12)
        self.assertTrue(lines[0].startswith("|"))
        self.assertTrue(lines[0].endswith("|"))

    def test_barcode_is_deterministic(self):
        label = {
            "fields": [{"type": "barcode", "x": 0, "y": 0, "height": 80, "data": "1Z999"}]
        }
        self.assertEqual(render_preview(label), render_preview(label))

    def test_later_fields_draw_over_earlier_ones(self):
        label = {
            "fields": [
                {"type": "box", "x": 0, "y": 0, "width": 80, "height": 2},
                {"type": "text", "x": 0, "y": 0, "data": "HI"},
            ]
        }
        self.assertEqual(render_preview(label), "HI" + "-" * 8 + "\n")

    def test_rejects_non_positive_scale(self):
        with self.assertRaises(ValueError):
            render_preview({"fields": []}, dots_per_col=0)

    def test_multiple_labels_get_headers(self):
        labels = [
            {"fields": [{"type": "text", "x": 0, "y": 0, "data": "A"}]},
            {"fields": [{"type": "text", "x": 0, "y": 0, "data": "B"}]},
        ]
        self.assertEqual(
            render_previews(labels),
            "--- label 1 of 2 ---\nA\n--- label 2 of 2 ---\nB\n",
        )


class PreviewCommandTests(unittest.TestCase):
    def _run(self, zpl: str, *extra):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "label.zpl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(zpl)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(["preview", path, *extra])
            return code, out.getvalue(), err.getvalue()

    def test_previews_a_label(self):
        code, out, _ = self._run("^XA\n^FO8,16\n^FDHELLO^FS\n^XZ\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "\n HELLO\n")

    def test_scale_flags(self):
        code, out, _ = self._run(
            "^XA\n^FO4,4\n^FDX^FS\n^XZ\n", "--dots-per-col", "2", "--dots-per-row", "2"
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "\n\n  X\n")

    def test_parse_errors_report_position(self):
        code, out, err = self._run("^XA\n^FOfifty,5\n^XZ\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("line 2, column 1", err)


if __name__ == "__main__":
    unittest.main()
