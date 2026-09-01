import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.config_loader import ConfigAssembler
from core.customizer import ConfigError, StructuredCopyAction, SystemConfigurator
from core.path_utils import project_root


class FakeChroot:
    def __init__(self, root: Path):
        self.chroot_path = root
        self.mode = "real"

    def run_command(self, _command):
        if _command == "cp -a /etc/skel/. /home/live/":
            source = self.chroot_path / "etc/skel"
            destination = self.chroot_path / "home/live"
            destination.mkdir(parents=True, exist_ok=True)
            if source.exists():
                shutil.copytree(source, destination, dirs_exist_ok=True)
        return ""


class TestCustomizerCopy(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="arch_builder_customizer_")
        self.rootfs = Path(self.tempdir.name) / "rootfs"
        self.rootfs.mkdir()
        self.chroot = FakeChroot(self.rootfs)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_xfce_copy_graph_places_expected_content_and_modes(self):
        config = ConfigAssembler(project_root() / "configs/global_build.json").assemble(
            "x86_64", target_desktop="xfce"
        )
        configurator = SystemConfigurator(self.chroot)
        configurator.load_from_config(config)
        existing_home = self.rootfs / "home/live"
        existing_home.mkdir(parents=True)
        (existing_home / ".bashrc").write_text("")

        configurator.apply()

        custom_root = project_root() / "configs/custom_files"
        common_rules = json.loads(
            (project_root() / "configs/base_customizations.json").read_text()
        )["base_copy_files"]
        desktop_rules = config.get("desktop_environment.copy_files")
        for rule in common_rules + desktop_rules:
            source = custom_root / rule["source"]
            destination = self.rootfs / rule["destination"].lstrip("/")
            if source.is_dir():
                for source_file in source.rglob("*"):
                    if not source_file.is_file() or source_file.name == ".gitkeep":
                        continue
                    copied = destination / source_file.relative_to(source)
                    self.assertTrue(copied.is_file(), copied)
                    self.assertEqual(copied.read_bytes(), source_file.read_bytes())
            else:
                self.assertEqual(destination.read_bytes(), source.read_bytes())

        self.assertFalse(
            (self.rootfs / "usr/share/applications/.gitkeep").exists()
        )
        self.assertEqual(
            (self.rootfs / "etc/sudoers.d/99-live-user").stat().st_mode & 0o7777,
            0o440,
        )
        self.assertEqual(
            (self.rootfs / "etc/vconsole.conf").stat().st_mode & 0o7777,
            0o644,
        )
        self.assertEqual(
            (self.rootfs / "usr/local/bin/create-install-icon.sh").stat().st_mode
            & 0o7777,
            0o755,
        )
        self.assertTrue(
            (self.rootfs / "usr/share/plymouth/themes/modern/modern.plymouth").is_file()
        )
        self.assertTrue(
            (self.rootfs / "usr/share/plymouth/themes/modern/background.png").is_file()
        )
        self.assertEqual(
            (self.rootfs / "home/live/.bashrc").read_bytes(),
            (custom_root / "desktops/xfce/etc/skel/.bashrc").read_bytes(),
        )

    def test_missing_structured_source_is_fatal(self):
        action = StructuredCopyAction(
            ".", [{"source": "missing", "destination": "/etc/missing"}], "x86_64"
        )

        with self.assertRaisesRegex(ConfigError, "source does not exist"):
            action.execute(self.chroot, Path(self.tempdir.name))

    def test_destination_cannot_escape_rootfs(self):
        source = Path(self.tempdir.name) / "source.conf"
        source.write_text("value\n")
        action = StructuredCopyAction(
            ".",
            [{"source": "source.conf", "destination": "/../../escaped.conf"}],
            "x86_64",
        )

        with self.assertRaisesRegex(ConfigError, "escapes its allowed root"):
            action.execute(self.chroot, Path(self.tempdir.name))


if __name__ == "__main__":
    unittest.main()
