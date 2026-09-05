# shipping-label-convert

Converts shipping label markup between ZPL (the language most thermal
label printers speak) and a plain JSON document.

ZPL is what comes out of a warehouse system or gets pasted into a
support ticket, and it is miserable to read or hand-edit: positional
commands, no whitespace requirements, and a syntax error a hundred
characters into a single-line file. This tool goes both ways - ZPL to
JSON so you can actually see what a label contains, and JSON to ZPL so
you can generate labels without gluing strings together by hand. When
the ZPL is malformed, the error tells you the exact line and column,
not just "invalid input".

Standard library only, no dependencies to install.

## Example

Given `label.zpl`:

```
^XA
^FO50,50
^A0N,30,30
^FDSHIP TO: Jane Doe^FS
^FO50,100
^BY2
^BCN,80
^FD1Z999AA10123456784^FS
^XZ
```

```
$ python -m shipping_label_convert.cli to-json label.zpl
{
  "fields": [
    {
      "x": 50,
      "y": 50,
      "font": "0",
      "orientation": "N",
      "height": 30,
      "width": 30,
      "type": "text",
      "data": "SHIP TO: Jane Doe"
    },
    {
      "x": 50,
      "y": 100,
      "type": "barcode",
      "symbology": "code128",
      "orientation": "N",
      "height": 80,
      "data": "1Z999AA10123456784"
    }
  ],
  "module_width": 2
}
```

Feeding that JSON back in with `to-zpl` regenerates equivalent ZPL.

## Error messages

A typo in a command name, or a field with no number where one is
expected, points straight at the offending character instead of
dumping a traceback:

```
$ python -m shipping_label_convert.cli to-json broken.zpl
broken.zpl:line 3, column 1: unknown command ^AZ (known commands: A, BC, BY, FD, FO, FS, FX, XA, XZ)
```

```
$ python -m shipping_label_convert.cli to-json broken2.zpl
broken2.zpl:line 2, column 1: expected a whole number for x position in ^FO, found 'fifty'
```

## Usage

```
python -m shipping_label_convert.cli to-json path/to/label.zpl
python -m shipping_label_convert.cli to-zpl path/to/label.json
```

Either subcommand accepts `-` to read from stdin. If you install the
package (`pip install .`), the same commands are available as
`shipping-label-convert to-json ...`.

## Supported ZPL commands

`^XA` `^XZ` `^FO` `^FD` `^FS` `^A` (font) `^BY` `^BC` (Code 128
barcode) `^FX` (comment). This covers a simple text-and-barcode label;
graphics, other barcode symbologies, and multi-label files aren't
handled yet.

## Status

Early. The ZPL parser's error messages are the part that's had real
care put into them; everything else is a first pass.
