#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the patch helper in disposable source trees."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hax-patches-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/patch.sh", self.root / "scripts/patch.sh")
        patch_dir = self.root / "patches/example"
        patch_dir.mkdir(parents=True)
        self.patch = patch_dir / "example.diff"
        self.patch.write_text(
            "diff --git a/first b/first\n"
            "--- a/first\n+++ b/first\n@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/second b/second\n"
            "--- a/second\n+++ b/second\n@@ -1 +1 @@\n-before\n+after\n"
        )
        (self.root / "first").write_text("old\n")
        (self.root / "second").write_text("before\n")

    def run_patch(self, *args, success=True):
        result = subprocess.run(
            ["sh", str(self.root / "scripts/patch.sh"), *args],
            cwd=self.root / "scripts", capture_output=True, text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result.stdout

    def test_list(self):
        self.assertEqual(self.run_patch("list"), "example\n")

    def test_round_trip_preserves_unrelated_edits(self):
        (self.root / "notes").write_text("local work\n")
        self.run_patch("check", "example")
        self.assertEqual((self.root / "first").read_text(), "old\n")
        self.run_patch("apply", "example")
        self.assertEqual((self.root / "first").read_text(), "new\n")
        self.assertEqual((self.root / "second").read_text(), "after\n")
        self.run_patch("apply", "example", success=False)
        self.run_patch("reverse", "example")
        self.assertEqual((self.root / "first").read_text(), "old\n")
        self.assertEqual((self.root / "second").read_text(), "before\n")
        self.assertEqual((self.root / "notes").read_text(), "local work\n")

    def test_conflict_does_not_partially_apply(self):
        (self.root / "second").write_text("local edit\n")
        self.run_patch("check", "example", success=False)
        self.run_patch("apply", "example", success=False)
        self.assertEqual((self.root / "first").read_text(), "old\n")
        self.assertEqual((self.root / "second").read_text(), "local edit\n")
        self.assertEqual(list(self.root.rglob("*.rej")), [])

    def test_reverse_conflict_does_not_partially_revert(self):
        self.run_patch("apply", "example")
        (self.root / "second").write_text("local edit\n")
        self.run_patch("reverse", "example", success=False)
        self.assertEqual((self.root / "first").read_text(), "new\n")
        self.assertEqual((self.root / "second").read_text(), "local edit\n")

    def test_invalid_selection(self):
        for args in [(), ("unknown",), ("apply",), ("list", "example"),
                     ("apply", "missing"), ("apply", "../example"),
                     ("apply", "--help"), ("apply", "example", "extra")]:
            with self.subTest(args=args):
                self.run_patch(*args, success=False)

    def test_ambiguous_version(self):
        shutil.copy2(self.patch, self.patch.with_name("other.diff"))
        self.run_patch("apply", "example", success=False)


if __name__ == "__main__":
    unittest.main()
