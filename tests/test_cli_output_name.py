import unittest
from unittest.mock import patch

from cli import (
    _config_path_from_argv,
    _resolve_output_name,
    _restore_invoking_user_ownership,
)
from core.path_utils import resolve_from_project


class TestCliOutputName(unittest.TestCase):
    def test_config_path_is_resolved_before_parser_defaults(self):
        self.assertEqual(
            _config_path_from_argv(["-c", "/tmp/custom-build.json"]),
            resolve_from_project("/tmp/custom-build.json"),
        )

    def test_explicit_output_is_preserved(self):
        self.assertEqual(
            _resolve_output_name("x86_64", "xfce", "/tmp/custom.iso"),
            "/tmp/custom.iso",
        )

    def test_default_output_includes_desktop_and_architecture(self):
        self.assertEqual(
            _resolve_output_name("x86_64", "xfce", None),
            str(resolve_from_project("output/arch-builder-xfce-x86_64.iso")),
        )

    def test_default_output_uses_base_when_desktop_missing(self):
        self.assertEqual(
            _resolve_output_name("x86_64", None, None),
            str(resolve_from_project("output/arch-builder-base-x86_64.iso")),
        )

    def test_default_output_sanitizes_desktop_and_architecture(self):
        self.assertEqual(
            _resolve_output_name("x86 64", "XFCE Plasma!", None),
            str(resolve_from_project("output/arch-builder-xfce-plasma-x86-64.iso")),
        )

    def test_relative_explicit_output_is_placed_in_output_directory(self):
        self.assertEqual(
            _resolve_output_name("x86_64", "xfce", "custom.iso"),
            str(resolve_from_project("output/custom.iso")),
        )

    def test_output_prefixed_path_is_not_duplicated(self):
        self.assertEqual(
            _resolve_output_name("x86_64", "xfce", "output/custom.iso"),
            str(resolve_from_project("output/custom.iso")),
        )

    @patch("cli.os.chown")
    @patch("cli.os.geteuid", return_value=0)
    @patch.dict("cli.os.environ", {"SUDO_UID": "1000", "SUDO_GID": "1001"})
    def test_root_build_artifacts_are_returned_to_sudo_user(
        self, _geteuid, chown
    ):
        paths = ["image.iso", "image.iso.sha256", "image.iso.md5"]

        _restore_invoking_user_ownership(paths)

        self.assertEqual(
            chown.call_args_list,
            [
                unittest.mock.call(path, 1000, 1001)
                for path in paths
            ],
        )


if __name__ == "__main__":
    unittest.main()
