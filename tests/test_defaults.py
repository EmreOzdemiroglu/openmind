#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Test personal compiled display defaults and validation gate."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DefaultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hax-defaults-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy2(ROOT / "config.def.h", self.root / "config.def.h")
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/generate_defaults.py", self.root / "scripts/generate_defaults.py")

    def run_gen(self, header_opt="", success=True):
        out_path = self.root / "compiled_defaults.h"
        res = subprocess.run(
            ["python3", str(self.root / "scripts/generate_defaults.py"), str(self.root), header_opt, str(out_path)],
            capture_output=True, text=True,
        )
        self.assertEqual(res.returncode == 0, success, res.stdout + res.stderr)
        return res

    def test_shipped_defaults(self):
        res = self.run_gen("")
        content = (self.root / "compiled_defaults.h").read_text()
        self.assertIn('#define HAX_DEFAULT_TINT "teal"', content)
        self.assertIn('#define HAX_DEFAULT_THEME "auto"', content)
        self.assertIn('#define HAX_DEFAULT_DISPLAY_WIDTH "auto"', content)
        self.assertIn('#define HAX_DEFAULT_MARKDOWN "1"', content)

    def test_custom_personal_header(self):
        (self.root / "config.h").write_text(
            '#define HAX_DEFAULTS_SCHEMA 1\n'
            '#define HAX_DEFAULT_TINT "rose"\n'
        )
        self.run_gen("config.h")
        content = (self.root / "compiled_defaults.h").read_text()
        self.assertIn('#define HAX_DEFAULT_TINT "rose"', content)
        self.assertIn('#define HAX_DEFAULT_THEME "auto"', content)

    def test_missing_schema_rejected(self):
        (self.root / "config.h").write_text('#define HAX_DEFAULT_TINT "rose"\n')
        res = self.run_gen("config.h", success=False)
        self.assertIn("missing HAX_DEFAULTS_SCHEMA", res.stderr)

    def test_invalid_schema_rejected(self):
        (self.root / "config.h").write_text(
            '#define HAX_DEFAULTS_SCHEMA 2\n'
            '#define HAX_DEFAULT_TINT "rose"\n'
        )
        res = self.run_gen("config.h", success=False)
        self.assertIn("unsupported HAX_DEFAULTS_SCHEMA", res.stderr)

    def test_invalid_choice_rejected(self):
        (self.root / "config.h").write_text(
            '#define HAX_DEFAULTS_SCHEMA 1\n'
            '#define HAX_DEFAULT_TINT "invalid"\n'
        )
        res = self.run_gen("config.h", success=False)
        self.assertIn("invalid HAX_DEFAULT_TINT value 'invalid'", res.stderr)

    def test_invalid_display_width_rejected(self):
        (self.root / "config.h").write_text(
            '#define HAX_DEFAULTS_SCHEMA 1\n'
            '#define HAX_DEFAULT_DISPLAY_WIDTH "10"\n'
        )
        res = self.run_gen("config.h", success=False)
        self.assertIn("invalid HAX_DEFAULT_DISPLAY_WIDTH", res.stderr)

    def test_missing_selected_header_rejected(self):
        res = self.run_gen("nonexistent.h", success=False)
        self.assertIn("does not exist", res.stderr)


if __name__ == "__main__":
    unittest.main()
