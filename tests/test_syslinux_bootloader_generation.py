import unittest
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


if __name__ == "__main__":
    unittest.main()
