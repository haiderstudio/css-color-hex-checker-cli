#!/usr/bin/env python3
"""Check hex colour values in CSS files are valid.

Run: python3 src/css_color_hex_checker.py styles.css
     python3 src/css_color_hex_checker.py project/
     python3 src/css_color_hex_checker.py --stdin < styles.css

A malformed hex colour is silently dropped by the
browser: the element falls back to an inherited or
default colour and the design breaks, with no error
anywhere. The cause is usually a typo — a digit too
few, a digit too many, or a letter that is not a hex
digit. This tool names each malformed value, with the
file and the line number, and exits 1 when any is
found, so it can fail a CI run. A file with no
malformed hex values exits 0.

A hex colour is a "#" followed by exactly 3, 4, 6 or
8 hex digits (0-9, a-f, A-F). Anything else that
looks like a colour value — "#12", "#gggggg",
"#12345", "#1234567" — is flagged. Only values are
checked: a "#" in a selector ("#main") is an id
selector, not a colour, so "#" tokens are only
checked when they sit in a declaration value, after
a ":" inside a rule block. "#" inside "url(...)" is
a fragment, not a colour, and is skipped. Comments
and strings are blanked out before the scan, so a
"#" inside either never counts.

It reads CSS only. It never edits a file, never
touches the network, and reads only the files and
folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CSS_SUFFIX = ".css"

_HEX = re.compile(r"#([A-Za-z0-9]*)")
_VALID_LENGTHS = (3, 4, 6, 8)
_HEX_DIGITS = set("0123456789abcdefABCDEF")


def blank_comments_and_strings(text):
    """Blank comments and string contents, keeping positions.

    Returns (clean, unclosed_comment). clean is a copy of
    the text the same length, where every comment
    (/* ... */) and every quoted string has its contents
    replaced by spaces. Newlines are kept, so a line
    number measured in the blanked text is the line
    number in the original. Blanked text is safe to scan
    for "#": a "#" inside a comment or a string (for
    example content: "#fff") is not a colour value.
    unclosed_comment is True when a "/*" never closes —
    the rest of the file is comment, so the blanked text
    blanks it to the end.
    """
    out = []
    unclosed = False
    i = 0
    size = len(text)
    while i < size:
        char = text[i]
        if char in ("\"", "'"):
            out.append(" ")
            i += 1
            while i < size and text[i] != char:
                if text[i] == "\\" and i + 1 < size:
                    out.append(" ")
                    out.append("\n" if text[i + 1] == "\n" else " ")
                    i += 2
                    continue
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < size:
                out.append(" ")
                i += 1
        elif char == "/" and i + 1 < size and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end == -1:
                unclosed = True
                for rest in text[i:]:
                    out.append("\n" if rest == "\n" else " ")
                i = size
            else:
                for rest in text[i:end + 2]:
                    out.append("\n" if rest == "\n" else " ")
                i = end + 2
        else:
            out.append(char)
            i += 1
    return "".join(out), unclosed


def _depths(clean):
    """Brace depth before each character of clean text.

    depth[i] is how many "{" are open just before
    character i. A "#" at depth 0 sits in a selector or
    an at-rule prelude, never in a declaration value.
    """
    depths = []
    depth = 0
    for char in clean:
        depths.append(depth)
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
    return depths


def _in_value(clean, index):
    """True when index sits in a declaration value.

    The text since the last ";" or "{" must hold a ":"
    — the colon that separates a property name from its
    value. A "#" in a selector, even inside a nested
    rule, has no such colon before it.
    """
    start = max(clean.rfind(";", 0, index),
                clean.rfind("{", 0, index))
    segment = clean[start + 1:index]
    return ":" in segment


def _in_url(clean, index):
    """True when the "#" is the fragment of a url(...)."""
    before = clean[:index].rstrip(" \t\r\n")
    return before.endswith("url(")


def check_text(text):
    """Check one document's text.

    Returns (findings, errors). A finding is {"line":
    int, "value": str, "reason": str}, in document
    order. An error is a plain string, for a file that
    cannot be parsed at all (an unclosed comment) — it
    fails the check the same way a finding does.
    """
    findings = []
    errors = []
    clean, unclosed = blank_comments_and_strings(text)
    if unclosed:
        errors.append("unclosed comment — a \"/*\" never closes")
    depths = _depths(clean)
    for match in _HEX.finditer(clean):
        index = match.start()
        if depths[index] < 1:
            continue
        if not _in_value(clean, index):
            continue
        if _in_url(clean, index):
            continue
        token = match.group(1)
        value = "#" + token
        if (len(token) not in _VALID_LENGTHS
                or any(char not in _HEX_DIGITS for char in token)):
            line = clean.count("\n", 0, index) + 1
            findings.append({
                "line": line,
                "value": value,
                "reason": ("is not a valid hex colour — use 3, 4, "
                           "6 or 8 hex digits"),
            })
    findings.sort(key=lambda item: item["line"])
    return findings, errors


def check_file(path):
    """Check one file. Returns (findings, errors)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], ["not valid UTF-8"]
    except OSError as exc:
        return [], [str(exc)]
    return check_text(text)


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of CSS files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .css
    only. .git folders are never walked, and directory
    links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    if not name.endswith(CSS_SUFFIX):
                        continue
                    candidate = Path(dirpath) / name
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one malformed value."""
    return ("FAIL %s: %s line %d %s"
            % (path, finding["value"], finding["line"],
               finding["reason"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no .css files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, errors = check_file(path)
        count = len(bad) + len(errors)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "errors": errors})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2))
    else:
        for result in results:
            for error in result["errors"]:
                print("FAIL %s: %s" % (result["path"], error))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d malformed hex value(s) "
                  "in %d file(s)." % (len(files), findings,
                                      files_with_findings))
        else:
            print("OK — %d file(s) checked, no malformed hex "
                  "values." % len(files))
    return 1 if findings else 0


def run_stdin(as_json=False):
    """Check one CSS document read from standard input."""
    text = sys.stdin.read()
    bad, errors = check_text(text)
    findings = len(bad) + len(errors)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": bad,
                        "errors": errors}],
             "checked": 1, "findings": findings},
            indent=2))
    else:
        for error in errors:
            print("FAIL <stdin>: %s" % error)
        for finding in bad:
            print(format_finding("<stdin>", finding))
        if findings:
            print("Checked 1 file(s), %d malformed hex value(s) "
                  "in 1 file(s)." % findings)
        else:
            print("OK — 1 file(s) checked, no malformed hex "
                  "values.")
    return 1 if findings else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="css_color_hex_checker",
        description="Check hex colour values in CSS files are "
                    "valid — # followed by 3, 4, 6 or 8 hex "
                    "digits — fail CI when one is not. "
                    "Report-only — it never edits a file.")
    parser.add_argument("paths", nargs="*",
                        help=".css files or folders to walk")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one CSS document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one .css file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
