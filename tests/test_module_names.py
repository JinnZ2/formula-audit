"""No module under glyph/ or kernel/ takes a standard-library name. Co-authored.

A script run from inside a package directory puts that directory first on
sys.path; a module there named like a standard-library one is then imported
in its place. glyph/operator.py did this to `operator` until it was renamed.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("glyph", "kernel")


def shadows(root=ROOT, packages=PACKAGES):
    names = sys.stdlib_module_names                        # Python 3.10+
    return sorted(str(p.relative_to(root)) for d in packages
                  for p in (root / d).rglob("*.py") if p.stem in names)


class TestModuleNames(unittest.TestCase):
    def test_no_module_shares_a_stdlib_name(self):
        self.assertEqual(shadows(), [])

    def test_the_packages_exist_and_hold_modules(self):
        for d in PACKAGES:
            self.assertTrue(list((ROOT / d).glob("*.py")), d)

    def test_a_planted_shadow_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "glyph").mkdir()
            (Path(t) / "kernel").mkdir()
            (Path(t) / "glyph" / "operator.py").write_text("")
            (Path(t) / "kernel" / "fine_name.py").write_text("")
            self.assertEqual(shadows(Path(t)), [str(Path("glyph") / "operator.py")])


if __name__ == "__main__":
    unittest.main()
