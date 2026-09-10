#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the patch helper in disposable source trees."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which("sh") or "/bin/sh"
MISSING_GIT_ERROR = "error: git required; install git to check, apply, or reverse patches"


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if shutil.which("git") is None:
            if os.environ.get("HAX_CI_REQUIRE_GIT"):
                raise AssertionError("git is required for the CI patch workflow")
            raise unittest.SkipTest("git not installed; skipping patch workflow tests")

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

    def run_patch(self, *args, success=True, env=None):
        result = subprocess.run(
            [SHELL, str(self.root / "scripts/patch.sh"), *args],
            cwd=self.root / "scripts", capture_output=True, text=True,
            env=env,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def gitless_env(self):
        bin_dir = self.root / "no-git-bin"
        bin_dir.mkdir()
        dirname = shutil.which("dirname")
        self.assertIsNotNone(dirname)
        (bin_dir / "dirname").symlink_to(dirname)
        env = os.environ.copy()
        env["PATH"] = str(bin_dir)
        return env

    def test_list(self):
        self.assertEqual(self.run_patch("list").stdout, "example\n")
        env = self.gitless_env()
        self.assertEqual(self.run_patch("list", env=env).stdout, "example\n")
        result = self.run_patch("apply", "example", success=False, env=env)
        self.assertEqual(result.stderr, MISSING_GIT_ERROR + "\n")

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
