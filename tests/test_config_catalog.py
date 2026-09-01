import json
import unittest
from pathlib import Path

from core.config_loader import ConfigAssembler


CONFIG_ROOT = Path("configs")


class TestConfigCatalog(unittest.TestCase):
    def test_every_json_is_an_object_without_duplicate_keys(self):
        for config_path in sorted(CONFIG_ROOT.rglob("*.json")):
            with self.subTest(config=str(config_path)):
                duplicate_keys = []

                def reject_duplicates(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            duplicate_keys.append(key)
                        result[key] = value
                    return result

                data = json.loads(
                    config_path.read_text(encoding="utf-8"),
                    object_pairs_hook=reject_duplicates,
                )
                self.assertIsInstance(data, dict)
                self.assertEqual(duplicate_keys, [])

    def test_every_desktop_profile_assembles(self):
        for profile in sorted((CONFIG_ROOT / "desktops").glob("*.json")):
            with self.subTest(profile=profile.stem):
                config = ConfigAssembler("configs").assemble(
                    "x86_64", target_desktop=profile.stem
                )
                self.assertEqual(config.get("desktop"), profile.stem)

    def test_every_desktop_copy_source_exists(self):
        base_rules = json.loads(
            (CONFIG_ROOT / "base_customizations.json").read_text()
        )["base_copy_files"]
        project_root = CONFIG_ROOT.resolve().parent
        for profile in sorted((CONFIG_ROOT / "desktops").glob("*.json")):
            with self.subTest(profile=profile.stem):
                data = json.loads(profile.read_text())
                self.assertIn("desktop_environment", data)
                desktop = data["desktop_environment"]
                self.assertTrue(desktop.get("use_common_config"))
                copy_root = project_root / desktop.get(
                    "customizations_path", "configs/custom_files"
                )
                rules = list(desktop.get("copy_files", []))
                if desktop.get("use_common_config"):
                    rules = base_rules + rules
                for rule in rules:
                    source = copy_root / rule["source"]
                    self.assertTrue(source.exists(), f"missing source: {source}")
                    self.assertTrue(
                        rule["destination"].startswith("/"),
                        f"destination must be absolute: {rule}",
                    )

    def test_every_package_profile_assembles(self):
        for profile in sorted((CONFIG_ROOT / "software").glob("*.json")):
            with self.subTest(profile=profile.stem):
                config = ConfigAssembler("configs").assemble(
                    "x86_64", package_profiles=[profile.stem]
                )
                self.assertIsInstance(config.get("software"), list)
                self.assertIsInstance(config.get("platform_specific.packages"), list)

    def test_non_desktop_profiles_have_matching_metadata(self):
        for folder in ("software", "services", "system", "boot", "initramfs"):
            for profile in sorted((CONFIG_ROOT / folder).glob("*.json")):
                with self.subTest(profile=str(profile)):
                    data = json.loads(profile.read_text(encoding="utf-8"))
                    self.assertEqual(data.get("name"), profile.stem)
                    self.assertIsInstance(data.get("description"), str)
                    self.assertTrue(data["description"])

    def test_global_defaults_reference_existing_profiles(self):
        data = json.loads(
            (CONFIG_ROOT / "global_build.json").read_text(encoding="utf-8")
        )
        defaults = data["defaults"]
        references = {
            "desktop": ("desktops", [defaults["desktop"]]),
            "kernel": ("system", [defaults["kernel"]]),
            "package_profiles": ("software", defaults["package_profiles"]),
            "service_profiles": ("services", defaults["service_profiles"]),
        }
        for key, (folder, names) in references.items():
            for name in names:
                with self.subTest(default=key, profile=name):
                    self.assertTrue((CONFIG_ROOT / folder / f"{name}.json").is_file())

    def test_non_desktop_configs_do_not_use_removed_legacy_keys(self):
        forbidden = {
            "build_environment",
            "components",
            "dependencies",
            "disabled_aur",
            "system_info",
        }

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from walk(child)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)

        for config_path in sorted(CONFIG_ROOT.rglob("*.json")):
            if "desktops" in config_path.parts:
                continue
            with self.subTest(config=str(config_path)):
                data = json.loads(config_path.read_text(encoding="utf-8"))
                self.assertFalse(forbidden.intersection(walk(data)))

    def test_local_package_sources_exist(self):
        project_root = CONFIG_ROOT.resolve().parent
        for profile in sorted((CONFIG_ROOT / "software").glob("*.json")):
            data = json.loads(profile.read_text(encoding="utf-8"))
            sources = data.get("package_sources", {})
            for package in sources.get("local_packages", []):
                with self.subTest(profile=profile.stem, package=package):
                    self.assertTrue((project_root / package).is_file())
            local_dir = sources.get("local_dir")
            if local_dir:
                with self.subTest(profile=profile.stem, local_dir=local_dir):
                    self.assertTrue((project_root / local_dir).is_dir())

    def test_hardware_profiles_have_supported_schema(self):
        formats = {
            "iso", "img", "raw", "qcow2", "vmdk", "vhd", "vhdx",
            "vdi", "tarball", "container",
        }
        for profile in sorted((CONFIG_ROOT / "hardware").glob("*.json")):
            with self.subTest(profile=profile.stem):
                data = json.loads(profile.read_text(encoding="utf-8"))
                self.assertTrue(data.get("name"))
                self.assertIn(data.get("architecture"), {"x86_64", "aarch64", "riscv64"})
                self.assertIn(data.get("output_format"), formats)
                self.assertIsInstance(data.get("bootloader"), dict)
                self.assertTrue(data["bootloader"].get("type"))

    def test_live_profiles_do_not_define_root_or_duplicate_users(self):
        for profile in sorted((CONFIG_ROOT / "live-users").glob("*.json")):
            data = json.loads(profile.read_text(encoding="utf-8"))
            users = data.get("customizations", {}).get("users", [])
            names = [user.get("name") for user in users]
            with self.subTest(profile=profile.stem):
                self.assertNotIn("root", names)
                self.assertEqual(len(names), len(set(names)))
        guest = json.loads(
            (CONFIG_ROOT / "live-users/guest.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("wheel", guest["customizations"]["users"][0]["groups"])

    def test_every_service_profile_assembles(self):
        for profile in sorted((CONFIG_ROOT / "services").glob("*.json")):
            with self.subTest(profile=profile.stem):
                config = ConfigAssembler("configs").assemble(
                    "x86_64", service_profiles=[profile.stem]
                )
                self.assertIsInstance(config.get("customizations.services"), list)

    def test_every_live_user_profile_has_unique_users(self):
        for profile in sorted((CONFIG_ROOT / "live-users").glob("*.json")):
            with self.subTest(profile=profile.stem):
                config = ConfigAssembler("configs").assemble(
                    "x86_64", target_desktop="xfce", target_live_profile=profile.stem
                )
                users = config.get("customizations.users")
                names = [user["name"] for user in users]
                self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
