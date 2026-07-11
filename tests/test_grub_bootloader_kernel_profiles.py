import unittest
from pathlib import Path

from core.bootloaders.grub2 import Grub2Bootloader
from core.config_loader import ConfigAssembler


class TestGrubBootloaderKernelProfiles(unittest.TestCase):
    def test_grub_supports_all_kernel_profiles(self):
        assembler = ConfigAssembler("configs")
        for profile, expected_kernel, expected_initramfs in [
            ("linux", "vmlinuz-linux", "initramfs-linux.img"),
            ("linux-lts", "vmlinuz-linux-lts", "initramfs-linux-lts.img"),
            ("linux-zen", "vmlinuz-linux-zen", "initramfs-linux-zen.img"),
            ("linux-hardened", "vmlinuz-linux-hardened", "initramfs-linux-hardened.img"),
        ]:
            with self.subTest(profile=profile):
                config = assembler.assemble(target_arch="x86_64", target_kernel=profile)
                loader = Grub2Bootloader(config, root_device_id="", iso_uuid="")
                replacements = loader._build_replacements(Path('.'))
                self.assertEqual(replacements["@@KERNEL_FILE@@"], expected_kernel)
                self.assertEqual(replacements["@@INITRAMFS_FILE@@"], expected_initramfs)


if __name__ == "__main__":
    unittest.main()
