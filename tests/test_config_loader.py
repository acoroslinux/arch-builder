import os
import unittest
from pathlib import Path

from core.config_loader import Config, ConfigAssembler, ConfigValidationError


class TestGlobalConfigLoader(unittest.TestCase):
    """Unit tests for the global configuration loader class and helpers."""

    def setUp(self):
        self.test_dir = Path("/tmp/arch_builder_test_configs")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        (self.test_dir / "architectures").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "desktops").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "kernels").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "packages").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "services").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "live-users").mkdir(parents=True, exist_ok=True)

        (self.test_dir / "global_build.json").write_text(
            '{"system": {"workdir_base": "/tmp/isofiles"}, "components": {"bootloaders": [{"name": "grub", "type": "module"}]}}'
        )
        (self.test_dir / "architectures/x86_64.json").write_text(
            '{"platform_specific": {"architecture": "x86_64", "base_kernel": "linux", "initramfs": "init.img", "packages": [{"name": "linux"}, {"name": "base"}]}}'
        )
        (self.test_dir / "desktops/xfce.json").write_text(
            '{"customizations": {"services": ["lightdm"]}}'
        )
        (self.test_dir / "kernels/linux-lts.json").write_text(
            '{"platform_specific": {"base_kernel": "linux-lts", "initramfs": "initramfs-linux-lts.img"}}'
        )
        (self.test_dir / "packages/base.json").write_text(
            '{"packages": ["git", "curl"]}'
        )
        (self.test_dir / "packages/networking.json").write_text(
            '{"packages": ["networkmanager", "resolvconf"]}'
        )
        (self.test_dir / "services/common.json").write_text(
            '{"customizations": {"services": ["sshd", "systemd-timesyncd"]}}'
        )
        (self.test_dir / "live-users/live-admin.json").write_text(
            '{"customizations": {"users": [{"name": "liveadmin", "groups": ["wheel", "video"], "password": "liveadmin"}]}}'
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.test_dir)

    def test_load_manifest_success(self):
        assembler = ConfigAssembler(str(self.test_dir))
        config = assembler.assemble("x86_64")
        self.assertIsInstance(config, Config)
        self.assertEqual(config.get("platform_specific.architecture"), "x86_64")

    def test_assemble_always_loads_base_packages(self):
        assembler = ConfigAssembler(str(self.test_dir))
        config = assembler.assemble("x86_64")
        self.assertIn("git", config.get("packages", []))
        self.assertIn("curl", config.get("packages", []))

    def test_assemble_with_desktop_and_package_profile(self):
        assembler = ConfigAssembler(str(self.test_dir))
        config = assembler.assemble(
            target_arch="x86_64",
            target_desktop="xfce",
            package_profiles=["networking"],
        )
        self.assertEqual(config.get("customizations.services"), ["lightdm"])
        self.assertIn("networkmanager", config.get("packages", []))

    def test_assemble_with_kernel_override(self):
        assembler = ConfigAssembler(str(self.test_dir))
        config = assembler.assemble(target_arch="x86_64", target_kernel="linux-lts")

        self.assertEqual(config.get("platform_specific.base_kernel"), "vmlinuz-linux-lts")
        self.assertEqual(config.get("platform_specific.initramfs"), "initramfs-linux-lts.img")

        kernel_entries = config.get("platform_specific.packages", [])
        names = [item.get("name") if isinstance(item, dict) else item for item in kernel_entries]
        self.assertIn("linux-lts", names)
        self.assertNotIn("linux", names)

    def test_real_config_contains_live_user_and_login_manager_files(self):
        assembler = ConfigAssembler("configs")
        config = assembler.assemble(target_arch="x86_64", target_desktop="xfce")

        users = config.get("customizations.users", [])
        user_names = [u.get("name") for u in users if isinstance(u, dict)]
        self.assertIn("live", user_names)

        file_rules = config.get("system_config.files", [])
        copied_dests = [r.get("dest") for r in file_rules if isinstance(r, dict)]
        self.assertIn("/etc/lightdm/lightdm.conf", copied_dests)

    def test_live_user_and_groups_override_updates_autologin_commands(self):
        assembler = ConfigAssembler("configs")
        config = assembler.assemble(
            target_arch="x86_64",
            target_desktop="xfce",
            live_user="demo",
            live_groups=["wheel", "audio", "video"],
        )

        users = config.get("customizations.users", [])
        names = [u.get("name") for u in users if isinstance(u, dict)]
        self.assertIn("demo", names)

        demo_user = next(u for u in users if isinstance(u, dict) and u.get("name") == "demo")
        self.assertEqual(demo_user.get("groups"), ["wheel", "audio", "video"])

        commands = config.get("system_config.commands", [])
        self.assertTrue(any("autologin-user=demo" in cmd for cmd in commands))
        self.assertTrue(any("AutomaticLogin=demo" in cmd for cmd in commands))
        self.assertTrue(any("User=demo" in cmd for cmd in commands))

    def test_live_profile_from_json_is_applied(self):
        assembler = ConfigAssembler(str(self.test_dir))
        config = assembler.assemble(
            target_arch="x86_64",
            target_live_profile="live-admin",
        )

        users = config.get("customizations.users", [])
        names = [u.get("name") for u in users if isinstance(u, dict)]
        self.assertIn("liveadmin", names)

        admin_user = next(
            u for u in users if isinstance(u, dict) and u.get("name") == "liveadmin"
        )
        self.assertEqual(admin_user.get("groups"), ["wheel", "video"])

    def test_service_profiles_are_merged_with_desktop_services(self):
        assembler = ConfigAssembler(str(self.test_dir))
        config = assembler.assemble(
            target_arch="x86_64",
            target_desktop="xfce",
            service_profiles=["common"],
        )

        services = config.get("customizations.services", [])
        self.assertIn("lightdm", services)
        self.assertIn("sshd", services)
        self.assertIn("systemd-timesyncd", services)


if __name__ == "__main__":
    print("\n=============================")
    print("RUNNING CONFIGURATION TESTS...")
    print("=============================\n")
    unittest.main()
