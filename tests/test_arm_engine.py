import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.config_loader import ConfigAssembler
from core.iso_engine import Arm64Engine


class TestArm64Engine(unittest.TestCase):
    def test_rpi4_mock_seeds_arm_kernel_and_filters_x86_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "airootfs"
            config = ConfigAssembler("configs").assemble(
                "aarch64",
                target_desktop="xfce",
                target_kernel="linux",
                package_profiles=["base", "custom-user", "xorg"],
            )
            toolchain = SimpleNamespace(
                mode="mock",
                iso_rootfs_path=root,
                build_chroot=Path(tmp) / "build_host",
            )
            engine = Arm64Engine("aarch64", config, toolchain)
            engine.setup_chroot(tmp)
            plan = engine._package_plan()

            self.assertTrue((root / "boot/Image").is_file())
            self.assertEqual(config.get("platform_specific.base_kernel"), "Image")
            self.assertNotIn("linux-aarch64", plan["official"])
            self.assertNotIn("linux", plan["official"])
            self.assertNotIn("archiso", plan["official"])
            self.assertEqual(plan["local_paths"], [])

    def test_arm_profile_assembles_without_x86_architecture_packages(self):
        config = ConfigAssembler("configs").assemble("aarch64")
        self.assertEqual(config.get("platform_specific.architecture"), "aarch64")
        self.assertEqual(config.get("arm_target.platform"), "rpi4")


if __name__ == "__main__":
    unittest.main()
