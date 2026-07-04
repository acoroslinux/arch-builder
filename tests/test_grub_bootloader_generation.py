import tempfile
import unittest
from pathlib import Path

from core.iso_engine import ArchEngine


class _ConfigStub:
    def get(self, key, default=None):
        values = {
            "system": {
                "binaries": {
                    "grub-mkrescue": "/usr/bin/grub-mkrescue",
                }
            },
            "system.iso_label": "ARCH-MODERN",
            "system.iso_uuid": "12345678-1234-1234-1234-123456789abc",
            "platform_specific.architecture": "x86_64",
            "platform_specific.base_kernel": "vmlinuz-linux",
            "platform_specific.initramfs": "initramfs-linux.img",
        }
        return values.get(key, default)


class _ToolchainStub:
    def __init__(self, chroot_path: Path):
        self.commands = []
        self.chroot_manager = type("Chroot", (), {"chroot_path": chroot_path})()

    def run_command(self, command, chroot_path=None):
        self.commands.append((command, chroot_path))
        return "ok"


class TestGrubBootloaderGeneration(unittest.TestCase):
    def test_build_bootloaders_generates_grub_cfg_and_uses_root_source(self):
        with tempfile.TemporaryDirectory(prefix="arch_builder_grub_") as tmp:
            root = Path(tmp)
            (root / "boot").mkdir(parents=True, exist_ok=True)

            toolchain = _ToolchainStub(root)
            engine = ArchEngine("x86_64", _ConfigStub(), toolchain)

            engine.build_bootloaders(str(root / "boot"))

            grub_cfg = root / "boot" / "grub" / "grub.cfg"
            self.assertTrue(grub_cfg.exists(), "grub.cfg should be generated in the active rootfs")

            command, chroot_path = toolchain.commands[-1]
            # Binary may be with or without full path
            self.assertTrue(command[0].endswith("grub-mkrescue"))
            self.assertEqual(command[-1], str(root / "tmp" / "arch-builder-iso-root"))
            self.assertIsNone(chroot_path)

    def test_grub_cfg_contains_archiso_uuid(self):
        with tempfile.TemporaryDirectory(prefix="arch_builder_grub_") as tmp:
            root = Path(tmp)
            (root / "boot").mkdir(parents=True, exist_ok=True)

            toolchain = _ToolchainStub(root)
            engine = ArchEngine("x86_64", _ConfigStub(), toolchain)

            engine.build_bootloaders(str(root / "boot"))

            grub_cfg = root / "boot" / "grub" / "grub.cfg"
            content = grub_cfg.read_text()
            self.assertIn("archisosearchuuid=12345678-1234-1234-1234-123456789abc", content)
            self.assertIn("/boot/vmlinuz-linux", content)

    def test_grub_cfg_has_correct_kernel_path(self):
        with tempfile.TemporaryDirectory(prefix="arch_builder_grub_") as tmp:
            root = Path(tmp)
            (root / "boot").mkdir(parents=True, exist_ok=True)

            toolchain = _ToolchainStub(root)
            engine = ArchEngine("x86_64", _ConfigStub(), toolchain)

            engine.build_bootloaders(str(root / "boot"))

            grub_cfg = root / "boot" / "grub" / "grub.cfg"
            content = grub_cfg.read_text()
            # Verify correct path format matching simpler /boot/ structure
            self.assertIn("/boot/", content)


if __name__ == "__main__":
    unittest.main()