# css-color-hex-checker-cli

Check hex colour values in CSS files are valid — # followed by exactly 3, 4, 6 or 8 hex digits — fail CI when one is not.

[![CI](https://github.com/haiderstudio/css-color-hex-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/css-color-hex-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`css_color_hex_checker` reads CSS files and reports
each malformed hex colour value — with the file and
the line number. It exits 1 when any malformed value
is found, so it can fail a CI run. A file with no
malformed hex values exits 0.

- A hex colour is a `#` followed by exactly 3, 4, 6
  or 8 hex digits (0-9, a-f, A-F). Anything else that
  looks like a colour value is flagged: `#12` (too
  few digits), `#gggggg` (a letter that is not a hex
  digit), `#12345` (five digits), `#1234567` (seven
  digits).
- A malformed hex colour is silently dropped by the
  browser: the element falls back to an inherited or
  default colour and the design breaks, with no error
  anywhere. A gate that names the exact value and
  line turns it into a few-characters fix.
- Only values are checked: a `#` in a selector, for
  example `#main`, is an id selector, not a colour,
  so a `#` token is only checked when it sits in a
  declaration value, after a `:` inside a rule block.
  A `#` inside `url(...)` is a fragment, not a
  colour, and is skipped.
- A `#` inside a comment or a string is never a
  colour value and is never flagged.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  files ending in `.css` only, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are
  never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one CSS document read from standard input.
- A file that cannot be parsed — an unclosed comment
  — is reported as an error and fails the check the
  same way a finding does.

## Who it is for

Anyone who writes a stylesheet. Malformed hex values
creep in after copy pastes, hand-typed colours, and
search-and-replace edits, and no one notices them
because the page still renders — just in the wrong
colour. This is the gate that names them at the pull
request, before they ship.

## What it does NOT do

- It does not check whether a colour has enough
  contrast. That is repo #12,
  colour-contrast-checker-cli — contrast is a
  different check on the same values.
- It does not check undefined `var(--name)`
  references, empty rules, or duplicate properties.
  Those are repos #121, css-var-checker-cli, #99,
  css-empty-rule-checker-cli, and #78,
  css-duplicate-property-checker-cli — different
  checks on the same files.
- It does not check whether a class is used in the
  HTML. That is repo #74, css-class-checker-cli,
  which checks UNUSED classes — a malformed colour
  is a different check on the same files.
- It does not convert colours between formats, and
  it does not generate palettes. Converters and
  palette tools (hexChecker, colorconv,
  prism-color-forge, colorhub) do that job — this
  tool only checks that a hex value in a stylesheet
  is well formed.
- It does not remove a malformed value or rewrite
  the file. It reports, you fix the digits.
- It never touches the network, and it only reads
  the files and folders you point it at.

## How this differs

- A fresh search of GitHub on Nov 16, 2026 found 0
  results for `"css-color-hex-checker-cli"` and 5
  results for `css color hex checker`, all converters
  or palette tools, none a checker:
  achyutghosh/hexChecker (0 stars, a colour palette
  picker website), ljiang9/colorconv (0 stars, a
  HEX/RGB/HSL converter with a WCAG contrast
  checker), krishyaa06/prism-color-forge (1 star, a
  colour toolkit: converter, Tailwind scale
  generator), theluckystrike/gen8x.com (0 stars, a
  palette generator), Akhilagovindu/colorhub (0
  stars, a palette web app). No rival checks hex
  validity in local CSS files.
- So the narrow slice stands: hex validity only,
  per-line reporting, a CI exit code, and a
  report-only tool that never edits a file.

## Install

```sh
git clone https://github.com/haiderstudio/css-color-hex-checker-cli.git
cd css-color-hex-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one stylesheet:

```sh
python3 src/css_color_hex_checker.py styles.css
```

A stylesheet with no malformed hex values passes:

```sh
$ python3 src/css_color_hex_checker.py examples/clean.css
OK — 1 file(s) checked, no malformed hex values.
```

A stylesheet with malformed values fails, with the
value and line for each one:

```sh
$ python3 src/css_color_hex_checker.py examples/flagged.css
FAIL examples/flagged.css: #12 line 4 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
FAIL examples/flagged.css: #gggggg line 5 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
FAIL examples/flagged.css: #12345 line 9 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
Checked 1 file(s), 3 malformed hex value(s) in 1 file(s).
```

Check a whole folder (`.css` files only):

```sh
$ python3 src/css_color_hex_checker.py examples/
FAIL examples/flagged.css: #12 line 4 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
FAIL examples/flagged.css: #gggggg line 5 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
FAIL examples/flagged.css: #12345 line 9 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
Checked 3 file(s), 3 malformed hex value(s) in 1 file(s).
```

Check one document from standard input:

```sh
$ printf 'a {\n  color: #fff;\n  background: #1234567;\n}\n' | python3 src/css_color_hex_checker.py --stdin
FAIL <stdin>: #1234567 line 3 is not a valid hex colour — use 3, 4, 6 or 8 hex digits
Checked 1 file(s), 1 malformed hex value(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/css_color_hex_checker.py --json examples/flagged.css
{
  "files": [
    {
      "path": "examples/flagged.css",
      "findings": [
        {
          "line": 4,
          "value": "#12",
          "reason": "is not a valid hex colour \u2014 use 3, 4, 6 or 8 hex digits"
        },
        {
          "line": 5,
          "value": "#gggggg",
          "reason": "is not a valid hex colour \u2014 use 3, 4, 6 or 8 hex digits"
        },
        {
          "line": 9,
          "value": "#12345",
          "reason": "is not a valid hex colour \u2014 use 3, 4, 6 or 8 hex digits"
        }
      ],
      "errors": []
    }
  ],
  "checked": 1,
  "findings": 3
}
```

Exit codes: 0 when no malformed hex value is found, 1
when any malformed value or parse error is found, 2
for a usage error (a missing path, a bad flag, or no
`.css` files found).

## Examples

An id selector, a `#` in a comment or a string, and a
`url()` fragment are not colour values —
`examples/edge.css` has all of them, and it passes:

```sh
$ python3 src/css_color_hex_checker.py examples/edge.css
OK — 1 file(s) checked, no malformed hex values.
```

All four valid lengths pass — 3, 4, 6 and 8 digits —
in one document:

```sh
$ printf 'a {\n  color: #abc;\n  border-color: #abcd;\n  background: #aabbcc;\n  outline-color: #aabbccdd;\n}\n' | python3 src/css_color_hex_checker.py --stdin
OK — 1 file(s) checked, no malformed hex values.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_css_color_hex_checker.py
```

The tests cover valid values (3, 4, 6 and 8 digits,
uppercase, mixed case, values in shorthand and in
gradients, several values on one line, a custom
property value), malformed values (1, 2, 5, 7 and 9
digits, a non-hex letter, a bare `#`, several in
order, the same one twice, inside `@media`, in
shorthand, in a gradient), things that are not
colours (id selectors, including long names, in
`@media` and nested, a `#` in a comment or a string,
a `url()` fragment with and without quotes, a `#`
before the colon, a nested id selector), parse errors
(an unclosed comment, a non-UTF-8 file), the CLI
(exit 0/1/2, folder walking for several CSS files,
nested folders, `--no-recursive`, `--exclude`, `.git`
skipped, a direct file checked whatever its name,
duplicate paths checked once, `--json` output,
`--stdin`, bad flags, missing paths, empty folders,
`--version`, input files left unchanged, the tool run
from `/` and under a fake HOME), the bundled examples
(sample output compared against a fresh run, and the
README-quoted outputs checked against it), and
hygiene checks (no placeholder text, no absolute
paths, no temp paths in any file, stdlib imports only,
no network use in the source, `.env` first in
`.gitignore`, CI file runs the test file, README names
the neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking a stylesheet is not new, and scanning
for `#` values is a standard technique — but no
existing tool does this one job, checking hex colour
validity in local CSS files as a tested command-line
gate, as the search above shows — and every line of
code here is original, built on nothing but Python's
standard library.
