import unittest

from cli import _resolve_output_name


class TestCliOutputName(unittest.TestCase):
    def test_explicit_output_is_preserved(self):
        self.assertEqual(
            _resolve_output_name("x86_64", "xfce", "/tmp/custom.iso"),
            "/tmp/custom.iso",
        )

    def test_default_output_includes_desktop_and_architecture(self):
        self.assertEqual(
            _resolve_output_name("x86_64", "xfce", None),
            "arch-builder-xfce-x86_64.iso",
        )

    def test_default_output_uses_base_when_desktop_missing(self):
        self.assertEqual(
            _resolve_output_name("x86_64", None, None),
            "arch-builder-base-x86_64.iso",
        )

    def test_default_output_sanitizes_desktop_and_architecture(self):
        self.assertEqual(
            _resolve_output_name("x86 64", "XFCE Plasma!", None),
            "arch-builder-xfce-plasma-x86-64.iso",
        )


if __name__ == "__main__":
    unittest.main()
