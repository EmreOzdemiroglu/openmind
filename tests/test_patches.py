#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the patch helper in disposable source trees."""

from pathlib import Path
import hashlib
import json
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
        shutil.copy2(ROOT / "scripts/patch_catalog.py", self.root / "scripts/patch_catalog.py")

        # Set up git repo in self.root so commit checks pass if needed
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)

        (self.root / "first").write_text("old\n")
        (self.root / "second").write_text("before\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=self.root, check=True)
        base_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.base_commit = base_commit

        patch_dir = self.root / "patches/example/1"
        patch_dir.mkdir(parents=True)
        self.patch = patch_dir / "example.diff"
        diff_content = (
            "diff --git a/first b/first\n"
            "--- a/first\n+++ b/first\n@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/second b/second\n"
            "--- a/second\n+++ b/second\n@@ -1 +1 @@\n-before\n+after\n"
        )
        self.patch.write_text(diff_content)
        sha256 = hashlib.sha256(diff_content.encode("utf-8")).hexdigest()

        meta = {
            "schema": 1,
            "feature": "example",
            "revision": 1,
            "base_commit": self.base_commit,
            "diff": "example.diff",
            "sha256": sha256,
            "requires": [],
            "conflicts": [],
            "status": "active",
        }
        (patch_dir / "patch.json").write_text(json.dumps(meta, indent=2))

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
        python3 = shutil.which("python3")
        self.assertIsNotNone(dirname)
        self.assertIsNotNone(python3)
        (bin_dir / "dirname").symlink_to(dirname)
        (bin_dir / "python3").symlink_to(python3)
        env = os.environ.copy()
        env["PATH"] = str(bin_dir)
        return env

    def test_list(self):
        self.assertEqual(self.run_patch("list").stdout, "example@1\n")
        env = self.gitless_env()
        self.assertEqual(self.run_patch("list", env=env).stdout, "example@1\n")
        result = self.run_patch("apply", "example", success=False, env=env)
        self.assertEqual(result.stderr, MISSING_GIT_ERROR + "\n")

    def test_inspect(self):
        out = self.run_patch("inspect", "example").stdout
        self.assertIn("Feature:     example", out)
        self.assertIn("Revision:    1", out)
        self.assertIn("Status:      active", out)
        out2 = self.run_patch("inspect", "example@1").stdout
        self.assertEqual(out, out2)
        self.run_patch("inspect", "example@2", success=False)
        self.run_patch("inspect", "missing", success=False)

    def test_catalog_check(self):
        out = self.run_patch("catalog-check").stdout
        self.assertIn("catalog OK (1 patches)", out)

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
                     ("apply", "--help"), ("apply", "example", "extra"),
                     ("apply", "example@0"), ("apply", "example@01")]:
            with self.subTest(args=args):
                self.run_patch(*args, success=False)

    def test_multiple_revisions_and_archived(self):
        patch_dir2 = self.root / "patches/example/2"
        patch_dir2.mkdir(parents=True)
        diff2 = patch_dir2 / "v2.diff"
        diff2.write_text("diff --git a/first b/first\n--- a/first\n+++ b/first\n@@ -1 +1 @@\n-old\n+v2\n")
        sha256_2 = hashlib.sha256(diff2.read_bytes()).hexdigest()

        # Mark rev 1 archived, rev 2 active
        meta1 = json.loads((self.root / "patches/example/1/patch.json").read_text())
        meta1["status"] = "archived"
        (self.root / "patches/example/1/patch.json").write_text(json.dumps(meta1))

        meta2 = {
            "schema": 1,
            "feature": "example",
            "revision": 2,
            "base_commit": self.base_commit,
            "diff": "v2.diff",
            "sha256": sha256_2,
            "requires": [],
            "conflicts": [],
            "status": "active",
        }
        (patch_dir2 / "patch.json").write_text(json.dumps(meta2))

        # Short selector selects rev 2 (the active one)
        insp_short = self.run_patch("inspect", "example").stdout
        self.assertIn("Revision:    2", insp_short)
        self.assertIn("Status:      active", insp_short)

        # Exact selector selects rev 1 (archived)
        insp_exact = self.run_patch("inspect", "example@1").stdout
        self.assertIn("Revision:    1", insp_exact)
        self.assertIn("Status:      archived", insp_exact)

        # List shows both
        list_out = self.run_patch("list").stdout
        self.assertIn("example@1 [archived]", list_out)
        self.assertIn("example@2", list_out)

    def test_validation_errors(self):
        import sys; sys.path.insert(0, str(ROOT)); import scripts.patch_catalog as pc
        # Digest mismatch
        meta = json.loads((self.root / "patches/example/1/patch.json").read_text())
        meta["sha256"] = "0" * 64
        (self.root / "patches/example/1/patch.json").write_text(json.dumps(meta))
        with self.assertRaises(pc.CatalogError):
            pc.load_catalog(self.root, check_commits=False)

        # Revert
        meta["sha256"] = hashlib.sha256(self.patch.read_bytes()).hexdigest()
        (self.root / "patches/example/1/patch.json").write_text(json.dumps(meta))
        pc.load_catalog(self.root, check_commits=False)

        # Multiple active revisions
        p2 = self.root / "patches/example/2"
        p2.mkdir()
        d2 = p2 / "2.diff"
        d2.write_text("dummy")
        meta2 = dict(meta, revision=2, diff="2.diff", sha256=hashlib.sha256(b"dummy").hexdigest())
        (p2 / "patch.json").write_text(json.dumps(meta2))
        with self.assertRaises(pc.CatalogError):
            pc.load_catalog(self.root, check_commits=False)

        # Missing requirement
        meta["status"] = "archived"
        (self.root / "patches/example/1/patch.json").write_text(json.dumps(meta))
        meta2["requires"] = ["other@1"]
        (p2 / "patch.json").write_text(json.dumps(meta2))
        with self.assertRaises(pc.CatalogError):
            pc.load_catalog(self.root, check_commits=False)


if __name__ == "__main__":
    unittest.main()

    def test_compare_catalogs_immutability(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import scripts.patch_catalog as pc

        old_cat = pc.load_catalog(self.root, check_commits=False)
        # Deep copy
        new_cat = json.loads(json.dumps(old_cat))

        # Unchanged passes
        pc.compare_catalogs(old_cat, new_cat)

        # Status change (active -> archived) is allowed
        new_cat["example"][1]["status"] = "archived"
        pc.compare_catalogs(old_cat, new_cat)

        # In-place base_commit change fails
        new_cat["example"][1]["base_commit"] = "0" * 40
        with self.assertRaises(pc.CatalogError):
            pc.compare_catalogs(old_cat, new_cat)

        # In-place sha256 change fails
        new_cat["example"][1]["base_commit"] = old_cat["example"][1]["base_commit"]
        new_cat["example"][1]["sha256"] = "1" * 64
        with self.assertRaises(pc.CatalogError):
            pc.compare_catalogs(old_cat, new_cat)

        # In-place requires change fails
        new_cat["example"][1]["sha256"] = old_cat["example"][1]["sha256"]
        new_cat["example"][1]["requires"] = ["foo@1"]
        with self.assertRaises(pc.CatalogError):
            pc.compare_catalogs(old_cat, new_cat)
