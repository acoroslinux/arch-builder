import tempfile
import unittest
from pathlib import Path
from core.bootloaders.syslinux import SyslinuxBootloader
from core.config_loader import ConfigAssembler


class TestSyslinuxBootloaderGeneration(unittest.TestCase):
    def test_syslinux_uses_selected_kernel_profile(self):
        assembler = ConfigAssembler("configs")
        config = assembler.assemble(target_arch="x86_64", target_kernel="linux-lts")

        loader = SyslinuxBootloader(config)
        replacements = loader._build_replacements()

        self.assertEqual(replacements["@@KERNEL_FILE@@"], "vmlinuz-linux-lts")
        self.assertEqual(replacements["@@INITRAMFS_FILE@@"], "initramfs-linux-lts.img")

    def test_syslinux_supports_all_kernel_profiles(self):
        assembler = ConfigAssembler("configs")
        for profile, expected_kernel, expected_initramfs in [
            ("linux", "vmlinuz-linux", "initramfs-linux.img"),
            ("linux-lts", "vmlinuz-linux-lts", "initramfs-linux-lts.img"),
            ("linux-zen", "vmlinuz-linux-zen", "initramfs-linux-zen.img"),
            ("linux-hardened", "vmlinuz-linux-hardened", "initramfs-linux-hardened.img"),
        ]:
            with self.subTest(profile=profile):
                config = assembler.assemble(target_arch="x86_64", target_kernel=profile)
                loader = SyslinuxBootloader(config)
                replacements = loader._build_replacements()
                self.assertEqual(replacements["@@KERNEL_FILE@@"], expected_kernel)
                self.assertEqual(replacements["@@INITRAMFS_FILE@@"], expected_initramfs)

    def test_syslinux_falls_back_to_default_kernel_when_missing_profile(self):
        assembler = ConfigAssembler("configs")
        config = assembler.assemble(target_arch="x86_64")

        loader = SyslinuxBootloader(config)
        replacements = loader._build_replacements()

        self.assertEqual(replacements["@@KERNEL_FILE@@"], "vmlinuz-linux")
        self.assertEqual(replacements["@@INITRAMFS_FILE@@"], "initramfs-linux.img")

    def test_syslinux_generates_only_its_config_without_unresolved_desktop(self):
        assembler = ConfigAssembler("configs")
        config = assembler.assemble(target_arch="x86_64", target_desktop="xfce")
        loader = SyslinuxBootloader(config)

        with tempfile.TemporaryDirectory(prefix="arch_builder_syslinux_") as tmp:
            workdir = Path(tmp)
            self.assertTrue(loader.prepare_files(workdir, iso_uuid="test-uuid"))
            generated = sorted(path.name for path in (workdir / "boot/syslinux").iterdir())
            self.assertEqual(generated, ["isolinux.cfg"])
            content = (workdir / "boot/syslinux/isolinux.cfg").read_text()
            self.assertIn("XFCE", content)
            self.assertNotIn("@@DESKTOP@@", content)
            self.assertNotIn("MENU BACKGROUND", content)


if __name__ == "__main__":
    unittest.main()
