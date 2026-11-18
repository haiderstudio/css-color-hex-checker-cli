#!/usr/bin/env python3
"""Tests for css_color_hex_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import css_color_hex_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def findings_of(text):
    return checker.check_text(text)


class TestValidValues(unittest.TestCase):
    def test_clean_file_passes(self):
        bad, errors = findings_of("body {\n  color: #1f2937;\n}\n")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_three_digit_passes(self):
        bad, _ = findings_of("a {\n  color: #fff;\n}\n")
        self.assertEqual(bad, [])

    def test_four_digit_passes(self):
        bad, _ = findings_of("a {\n  color: #abcd;\n}\n")
        self.assertEqual(bad, [])

    def test_six_digit_passes(self):
        bad, _ = findings_of("a {\n  color: #2563eb;\n}\n")
        self.assertEqual(bad, [])

    def test_eight_digit_passes(self):
        bad, _ = findings_of("a {\n  color: #2563ebcc;\n}\n")
        self.assertEqual(bad, [])

    def test_uppercase_passes(self):
        bad, _ = findings_of("a {\n  color: #ABCDEF;\n}\n")
        self.assertEqual(bad, [])

    def test_mixed_case_passes(self):
        bad, _ = findings_of("a {\n  color: #aB3;\n}\n")
        self.assertEqual(bad, [])

    def test_value_in_shorthand_passes(self):
        bad, _ = findings_of(
            "a {\n  border: 1px solid #ccc;\n}\n")
        self.assertEqual(bad, [])

    def test_value_in_gradient_passes(self):
        bad, _ = findings_of(
            "a {\n  background: linear-gradient(#fff, #000);\n}\n")
        self.assertEqual(bad, [])

    def test_several_values_one_line_pass(self):
        bad, _ = findings_of(
            "a {\n  box-shadow: 0 0 2px #000, 0 0 4px #fff;\n}\n")
        self.assertEqual(bad, [])

    def test_custom_property_value_passes(self):
        bad, _ = findings_of(
            ":root {\n  --brand: #2563eb;\n}\n")
        self.assertEqual(bad, [])


class TestMalformedValues(unittest.TestCase):
    def test_two_digits_flagged(self):
        bad, _ = findings_of("a {\n  color: #12;\n}\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 2)
        self.assertEqual(bad[0]["value"], "#12")
        self.assertIn("not a valid hex colour", bad[0]["reason"])

    def test_five_digits_flagged(self):
        bad, _ = findings_of("a {\n  color: #12345;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#12345"])

    def test_seven_digits_flagged(self):
        bad, _ = findings_of("a {\n  color: #1234567;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#1234567"])

    def test_nine_digits_flagged(self):
        bad, _ = findings_of("a {\n  color: #123456789;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#123456789"])

    def test_one_digit_flagged(self):
        bad, _ = findings_of("a {\n  color: #1;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#1"])

    def test_non_hex_letter_flagged(self):
        bad, _ = findings_of("a {\n  color: #gggggg;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#gggggg"])

    def test_non_hex_letter_in_short_value(self):
        bad, _ = findings_of("a {\n  color: #ffg;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#ffg"])

    def test_bare_hash_flagged(self):
        bad, _ = findings_of("a {\n  color: #;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#"])

    def test_several_malformed_in_order(self):
        bad, _ = findings_of(
            "a {\n  color: #12;\n  background: #gggggg;\n}\n"
            "b {\n  border-color: #12345;\n}\n")
        self.assertEqual([item["value"] for item in bad],
                         ["#12", "#gggggg", "#12345"])
        self.assertEqual([item["line"] for item in bad], [2, 3, 6])

    def test_same_malformed_twice_reported_twice(self):
        bad, _ = findings_of(
            "a {\n  color: #12;\n}\n"
            "b {\n  color: #12;\n}\n")
        self.assertEqual(len(bad), 2)

    def test_malformed_in_media_block_flagged(self):
        bad, _ = findings_of(
            "@media (max-width: 600px) {\n"
            "  a {\n    color: #12;\n  }\n}\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)

    def test_malformed_in_shorthand_flagged(self):
        bad, _ = findings_of(
            "a {\n  border: 1px solid #12;\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#12"])

    def test_malformed_in_gradient_flagged(self):
        bad, _ = findings_of(
            "a {\n  background: linear-gradient(#fff, #12);\n}\n")
        self.assertEqual([item["value"] for item in bad], ["#12"])

    def test_empty_document_passes(self):
        bad, errors = findings_of("")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_unclosed_comment_is_error(self):
        bad, errors = findings_of(
            "/* never closes\n"
            "a {\n  color: #12;\n}\n")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("unclosed comment", errors[0])


class TestNotColours(unittest.TestCase):
    def test_id_selector_not_flagged(self):
        bad, _ = findings_of("#main {\n  color: red;\n}\n")
        self.assertEqual(bad, [])

    def test_id_selector_with_long_name_not_flagged(self):
        bad, _ = findings_of("#sidebar1234567 {\n  color: red;\n}\n")
        self.assertEqual(bad, [])

    def test_id_selector_in_media_not_flagged(self):
        bad, _ = findings_of(
            "@media (max-width: 600px) {\n"
            "  #main {\n    color: red;\n  }\n}\n")
        self.assertEqual(bad, [])

    def test_hash_in_comment_not_flagged(self):
        bad, _ = findings_of(
            "/* #gggggg */\n"
            "a {\n  color: red;\n}\n")
        self.assertEqual(bad, [])

    def test_hash_in_string_not_flagged(self):
        bad, _ = findings_of(
            'a::before {\n  content: "#12";\n}\n')
        self.assertEqual(bad, [])

    def test_hash_in_url_fragment_not_flagged(self):
        bad, _ = findings_of(
            "a {\n  background: url(#sprite);\n}\n")
        self.assertEqual(bad, [])

    def test_hash_in_url_with_quotes_not_flagged(self):
        bad, _ = findings_of(
            "a {\n  background: url('#sprite');\n}\n")
        self.assertEqual(bad, [])

    def test_hash_before_colon_not_a_value(self):
        bad, _ = findings_of(
            "a {\n  #weird: 1;\n}\n")
        self.assertEqual(bad, [])

    def test_nested_id_selector_not_flagged(self):
        bad, _ = findings_of(
            ".wrap {\n  #inner {\n    color: red;\n  }\n}\n")
        self.assertEqual(bad, [])


class TestCli(unittest.TestCase):
    def test_clean_file_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.css",
                         "a {\n  color: #fff;\n}\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_flagged_file_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.css",
                         ".x {\n  color: #12;\n}\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("FAIL %s: #12 line 2" % path, out)
            self.assertIn("1 malformed hex value(s)", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.css", "a {\n  color: #fff;\n}\n")
            write(tmp, "b.css", ".x {\n  color: #12;\n}\n")
            write(tmp, "notes.txt", ".y {\n  color: #12;\n}\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s)", out)

    def test_nested_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/deep.css",
                  ".x {\n  color: #12;\n}\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("#12", out)

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.css", "a {\n  color: #fff;\n}\n")
            write(tmp, "sub/deep.css",
                  ".x {\n  color: #12;\n}\n")
            code, out, _ = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.css", ".x {\n  color: #12;\n}\n")
            write(tmp, "skip.css", ".y {\n  color: #12;\n}\n")
            code, out, _ = run_cli(["--exclude", "skip.css", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/bad.css",
                  ".x {\n  color: #12;\n}\n")
            write(tmp, "a.css", "a {\n  color: #fff;\n}\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "style.txt",
                         ".x {\n  color: #12;\n}\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("#12", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.css",
                         ".x {\n  color: #12;\n}\n")
            code, out, _ = run_cli([path, path])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.css",
                         ".x {\n  color: #12;\n}\n")
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(data["files"][0]["findings"][0]["value"],
                             "#12")
            self.assertEqual(data["files"][0]["findings"][0]["line"], 2)

    def test_stdin(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(
            "a {\n  color: #fff;\n  background: #1234567;\n}\n")
        try:
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>: #1234567 line 3", out)

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("a {\n  color: #fff;\n}\n")
        try:
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("no malformed", out)

    def test_bad_flags(self):
        code, _, err = run_cli(["--no-such-flag"])
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)

    def test_missing_path(self):
        code, _, err = run_cli(["no-such-file.css"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no .css files found", err)

    def test_no_paths(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("give at least one", err)

    def test_stdin_with_paths_rejected(self):
        code, _, err = run_cli(["--stdin", "a.css"])
        self.assertEqual(code, 2)
        self.assertIn("--stdin takes no file", err)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("css_color_hex_checker 1.0.0", out)

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.css", b"\xff\xfe\x00bad")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = ".x {\n  color: #12;\n}\n"
            path = write(tmp, "a.css", text)
            run_cli([path])
            self.assertEqual(Path(path).read_text(), text)

    def test_run_from_root_and_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.css", "a {\n  color: #fff;\n}\n")
            env = dict(os.environ)
            env["HOME"] = tmp
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src" / "css_color_hex_checker.py"), path],
                capture_output=True, text=True, cwd="/", env=env)
            self.assertEqual(result.returncode, 0)
            self.assertIn("no malformed", result.stdout)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        sample = (REPO / "examples" / "sample-output.md").read_text()
        result = subprocess.run(
            ["sh", str(REPO / "examples" / "run-example.sh")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), sample.strip())

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        flagged = (REPO / "examples" / "flagged.css").read_text()
        bad, _ = checker.check_text(flagged)
        for item in bad:
            line = ("FAIL examples/flagged.css: %s line %d %s"
                    % (item["value"], item["line"], item["reason"]))
            self.assertIn(line, readme)

    def test_clean_example_passes(self):
        code, _, _ = run_cli([str(REPO / "examples" / "clean.css")])
        self.assertEqual(code, 0)

    def test_flagged_example_fails_with_three(self):
        flagged = (REPO / "examples" / "flagged.css").read_text()
        bad, _ = checker.check_text(flagged)
        self.assertEqual(len(bad), 3)
        self.assertEqual([item["value"] for item in bad],
                         ["#12", "#gggggg", "#12345"])

    def test_edge_example_passes(self):
        code, _, _ = run_cli([str(REPO / "examples" / "edge.css")])
        self.assertEqual(code, 0)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True):
        """Every file in the repo, minus .git and caches."""
        for path in REPO.rglob("*"):
            if path.is_dir():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix == ".pyc":
                continue
            if skip_tests and "tests" in path.parts:
                continue
            yield path

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_temp_paths_in_files(self):
        hits = []
        for path in self._repo_files(skip_tests=False):
            text = path.read_text(errors="ignore")
            if "/t" + "mp/" in text:
                hits.append(str(path))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src" / "css_color_hex_checker.py",
                       REPO / "tests" / "test_css_color_hex_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"css_color_hex_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src" / "css_color_hex_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertTrue(lines, ".gitignore is empty")
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("tests/test_css_color_hex_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        for name in ("css-class-checker-cli",
                     "css-duplicate-property-checker-cli",
                     "css-empty-rule-checker-cli"):
            self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
