import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.path_utils import resolve_from_project

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConfigLoader")


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""


class Config:
    """
    Data wrapper for configuration objects with dot-notation access.
    """

    def __init__(self, data: Union[Dict[str, Any], "Config"]):
        if isinstance(data, Config):
            self._data = data._data
        else:
            self._data = data

    def get(self, path: str, default: Any = None) -> Any:
        keys = path.split(".")
        current = self._data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif hasattr(current, "_data"):
                current = (
                    current._data.get(key) if isinstance(current._data, dict) else None
                )
            else:
                return default

            if current is None:
                return default
        return current

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            val = self._data[name]
            return Config(val) if isinstance(val, dict) else val
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __getitem__(self, item):
        return self._data[item]

    def __repr__(self):
        return f"Config({self._data})"

    def to_dict(self) -> Dict[str, Any]:
        return self._data


class ConfigAssembler:
    """
    The assembler is the composition brain.
    It reads the global manifest and merges the configuration of all components
    (architectures, desktops, bootloaders, and so on) into a single
    configuration object.
    """

    def __init__(self, config_root: str):
        configured_path = resolve_from_project(config_root)
        if configured_path.suffix.lower() == ".json":
            self.manifest_path = configured_path
            self.config_root = configured_path.parent
        else:
            self.config_root = configured_path
            self.manifest_path = self.config_root / "global_build.json"
        self.master_config: Dict[str, Any] = {}

    def _deep_merge(
        self,
        base: Dict[str, Any],
        update: Dict[str, Any],
        path: tuple = (),
    ) -> Dict[str, Any]:
        """Recursively merge two dictionaries and combine lists without losing data."""
        for key, value in update.items():
            current_path = (*path, key)
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key] = self._deep_merge(base[key], value, current_path)
            elif (
                isinstance(value, list) and key in base and isinstance(base[key], list)
            ):
                if current_path == ("customizations", "users"):
                    for item in value:
                        if not isinstance(item, dict) or not item.get("name"):
                            if item not in base[key]:
                                base[key].append(deepcopy(item))
                            continue
                        existing_index = next(
                            (
                                index
                                for index, existing in enumerate(base[key])
                                if isinstance(existing, dict)
                                and existing.get("name") == item["name"]
                            ),
                            None,
                        )
                        if existing_index is None:
                            base[key].append(deepcopy(item))
                        else:
                            base[key][existing_index] = deepcopy(item)
                    continue
                # Extend lists while avoiding duplicates where simple checks work.
                for item in value:
                    if item not in base[key]:
                        base[key].append(deepcopy(item))
            else:
                base[key] = deepcopy(value)
        return base

    def _load_json_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise ConfigValidationError(f"Configuration file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ConfigValidationError(f"Error reading {path}: {e}") from e
        if not isinstance(data, dict):
            raise ConfigValidationError(
                f"Configuration root must be an object: {path}"
            )
        return data

    def _load_optional_profile(
        self, category: str, profile_name: str, required: bool = False
    ) -> Dict[str, Any]:
        """Load a profile JSON from configs/<category>/<profile_name>.json if it exists."""
        profile_path = self.config_root / category / f"{profile_name}.json"
        if not profile_path.exists() and category == "software":
            profile_path = self.config_root / "packages" / f"{profile_name}.json"
        elif not profile_path.exists() and category == "system":
            profile_path = self.config_root / "kernels" / f"{profile_name}.json"
        if not profile_path.exists():
            if required:
                raise ConfigValidationError(
                    f"Profile '{profile_name}' not found in '{category}': {profile_path}"
                )
            logger.warning(
                f"Profile '{profile_name}' not found in '{category}' at {profile_path}"
            )
            return {}
        data = self._load_json_file(profile_path)
        configured_name = data.get("name")
        if configured_name is not None and configured_name != profile_name:
            raise ConfigValidationError(
                f"Profile name mismatch in {profile_path}: "
                f"expected '{profile_name}', found '{configured_name}'"
            )
        return data

    @staticmethod
    def _packages(config: Dict[str, Any]) -> List[Any]:
        return config.get("software", config.get("packages", []))

    def _apply_kernel_override(self, kernel_name: str) -> None:
        """Set selected kernel and align related fields in platform_specific."""
        platform = self.master_config.setdefault("platform_specific", {})
        kernel_package = kernel_name.removeprefix("vmlinuz-")
        # Convert kernel package name to kernel filename (e.g., "linux" -> "vmlinuz-linux")
        base_kernel = f"vmlinuz-{kernel_package}"
        platform["base_kernel"] = base_kernel

        # Keep initramfs naming coherent with selected kernel.
        platform["initramfs"] = f"initramfs-{kernel_package}.img"

        kernel_candidates = {"linux", "linux-lts", "linux-zen", "linux-hardened"}

        def replace_kernel_in_list(pkg_list):
            replaced = False
            for idx, item in enumerate(pkg_list):
                if isinstance(item, dict):
                    name = item.get("name")
                    if name in kernel_candidates:
                        pkg_list[idx] = {**item, "name": kernel_package}
                        replaced = True
                elif isinstance(item, str) and item in kernel_candidates:
                    pkg_list[idx] = kernel_package
                    replaced = True
            if not replaced:
                if pkg_list and isinstance(pkg_list[0], dict):
                    pkg_list.append({"name": kernel_package})
                else:
                    pkg_list.append(kernel_package)
            return replaced

        for container in (platform, self.master_config):
            for package_key in ("packages", "software"):
                package_list = container.get(package_key)
                if isinstance(package_list, list):
                    replace_kernel_in_list(package_list)

    def _apply_live_user_override(
        self, live_user: str, live_groups: Optional[List[str]] = None
    ) -> None:
        """Override live user identity/groups and keep display-manager autologin aligned."""
        customizations = self.master_config.setdefault("customizations", {})
        users = customizations.setdefault("users", [])

        if not isinstance(users, list) or not users:
            users = []
            customizations["users"] = users

        target_idx = None
        for idx, user in enumerate(users):
            if isinstance(user, dict) and user.get("name") == "live":
                target_idx = idx
                break

        if target_idx is None:
            if users:
                target_idx = 0
            else:
                users.append({"name": live_user, "password": "live", "groups": []})
                target_idx = 0

        target_user = users[target_idx]
        if not isinstance(target_user, dict):
            target_user = {}
            users[target_idx] = target_user

        target_user["name"] = live_user
        if live_groups is not None:
            target_user["groups"] = [g for g in live_groups if g]

        commands = self.master_config.setdefault("system_config", {}).setdefault(
            "commands", []
        )
        if not isinstance(commands, list):
            commands = []
            self.master_config["system_config"]["commands"] = commands

        autologin_commands = [
            (
                "if [ -f /etc/lightdm/lightdm.conf ]; then "
                f"sed -i 's/^autologin-user=.*/autologin-user={live_user}/' /etc/lightdm/lightdm.conf; fi"
            ),
            (
                "if [ -f /etc/gdm/custom.conf ]; then "
                "sed -i 's/^AutomaticLogin=.*/"
                f"AutomaticLogin={live_user}/' /etc/gdm/custom.conf; fi"
            ),
            (
                "if [ -f /etc/sddm.conf.d/autologin.conf ]; then "
                f"sed -i 's/^User=.*/User={live_user}/' /etc/sddm.conf.d/autologin.conf; fi"
            ),
        ]
        for cmd in autologin_commands:
            if cmd not in commands:
                commands.append(cmd)

    def _resolve_live_user_from_config(self) -> Optional[Dict[str, Any]]:
        """Return the primary live-user dict from current merged configuration."""
        customizations = self.master_config.get("customizations", {})
        if not isinstance(customizations, dict):
            return None

        users = customizations.get("users", [])
        if not isinstance(users, list) or not users:
            return None

        for user in users:
            if isinstance(user, dict) and user.get("name"):
                return user
        return None

    def _validate_assembled(self, target_arch: str) -> None:
        """Validate the contracts consumed by the build engines."""
        platform = self.master_config.get("platform_specific")
        if not isinstance(platform, dict):
            raise ConfigValidationError("Missing object: platform_specific")

        configured_arch = platform.get("architecture")
        if configured_arch != target_arch:
            raise ConfigValidationError(
                "Architecture profile mismatch: "
                f"requested '{target_arch}', configured '{configured_arch}'"
            )

        for container_name, container in (
            ("root", self.master_config),
            ("platform_specific", platform),
        ):
            for package_key in ("software", "packages"):
                packages = container.get(package_key)
                if packages is None:
                    continue
                if not isinstance(packages, list):
                    raise ConfigValidationError(
                        f"{container_name}.{package_key} must be a list"
                    )
                for item in packages:
                    if isinstance(item, str) and item:
                        continue
                    if isinstance(item, dict) and item.get("name"):
                        continue
                    raise ConfigValidationError(
                        f"Invalid package entry in {container_name}.{package_key}: {item!r}"
                    )

        customizations = self.master_config.get("customizations", {})
        if not isinstance(customizations, dict):
            raise ConfigValidationError("customizations must be an object")

        users = customizations.get("users", [])
        if not isinstance(users, list):
            raise ConfigValidationError("customizations.users must be a list")
        user_names = []
        for user in users:
            if not isinstance(user, dict) or not user.get("name"):
                raise ConfigValidationError(
                    f"Invalid customizations.users entry: {user!r}"
                )
            user_names.append(user["name"])
        duplicates = sorted(
            name for name in set(user_names) if user_names.count(name) > 1
        )
        if duplicates:
            raise ConfigValidationError(
                f"Duplicate users after configuration merge: {', '.join(duplicates)}"
            )

        services = customizations.get("services", [])
        if not isinstance(services, list) or not all(
            isinstance(service, str) and service for service in services
        ):
            raise ConfigValidationError(
                "customizations.services must be a list of non-empty strings"
            )

        for field in ("hostname", "timezone", "locale", "keymap"):
            value = customizations.get(field)
            if value is not None and (not isinstance(value, str) or not value):
                raise ConfigValidationError(
                    f"customizations.{field} must be a non-empty string"
                )

        for user in users:
            groups = user.get("groups", [])
            if not isinstance(groups, list) or not all(
                isinstance(group, str) and group for group in groups
            ):
                raise ConfigValidationError(
                    f"groups for user '{user['name']}' must be non-empty strings"
                )
            password = user.get("password")
            if password is not None and not isinstance(password, str):
                raise ConfigValidationError(
                    f"password for user '{user['name']}' must be a string"
                )

        package_sources = self.master_config.get("package_sources", {})
        if not isinstance(package_sources, dict):
            raise ConfigValidationError("package_sources must be an object")
        for key in ("official", "aur", "local_packages"):
            values = package_sources.get(key, [])
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value for value in values
            ):
                raise ConfigValidationError(
                    f"package_sources.{key} must be a list of non-empty strings"
                )
        for key in ("local_dir", "local_glob"):
            value = package_sources.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                raise ConfigValidationError(
                    f"package_sources.{key} must be a non-empty string"
                )
        for package_path in package_sources.get("local_packages", []):
            resolved_package = resolve_from_project(package_path)
            if not resolved_package.is_file():
                raise ConfigValidationError(
                    f"Configured local package not found: {package_path}"
                )
        local_dir = package_sources.get("local_dir")
        if local_dir and not resolve_from_project(local_dir).is_dir():
            raise ConfigValidationError(
                f"Configured local package directory not found: {local_dir}"
            )

        initramfs = self.master_config.get("initramfs_config")
        if initramfs is not None:
            if not isinstance(initramfs, dict):
                raise ConfigValidationError("initramfs_config must be an object")
            for key in ("modules", "binaries", "files", "hooks"):
                values = initramfs.get(key, [])
                if not isinstance(values, list) or not all(
                    isinstance(value, str) and value for value in values
                ):
                    raise ConfigValidationError(
                        f"initramfs_config.{key} must be a list of non-empty strings"
                    )
            if not initramfs.get("hooks"):
                raise ConfigValidationError("initramfs_config.hooks cannot be empty")

        system_config = self.master_config.get("system_config", {})
        if not isinstance(system_config, dict):
            raise ConfigValidationError("system_config must be an object")
        commands = system_config.get("commands", [])
        if not isinstance(commands, list) or not all(
            isinstance(command, str) and command for command in commands
        ):
            raise ConfigValidationError(
                "system_config.commands must be a list of non-empty strings"
            )
        files = system_config.get("files", [])
        if not isinstance(files, list):
            raise ConfigValidationError("system_config.files must be a list")
        for rule in files:
            if not isinstance(rule, dict):
                raise ConfigValidationError(
                    f"Invalid system_config.files entry: {rule!r}"
                )
            src, dest, mode = rule.get("src"), rule.get("dest"), rule.get("mode")
            if not isinstance(src, str) or not src:
                raise ConfigValidationError("system_config.files src is required")
            if not resolve_from_project(src).exists():
                raise ConfigValidationError(
                    f"system_config.files source not found: {src}"
                )
            if not isinstance(dest, str) or not dest.startswith("/"):
                raise ConfigValidationError(
                    f"system_config.files dest must be absolute: {dest!r}"
                )
            if mode is not None:
                try:
                    parsed_mode = int(str(mode), 8)
                except ValueError as exc:
                    raise ConfigValidationError(
                        f"Invalid system_config.files mode: {mode!r}"
                    ) from exc
                if parsed_mode < 0 or parsed_mode > 0o7777:
                    raise ConfigValidationError(
                        f"Invalid system_config.files mode: {mode!r}"
                    )

        bootloader = self.master_config.get("bootloader")
        if bootloader is not None and (
            not isinstance(bootloader, dict)
            or not isinstance(bootloader.get("type"), str)
            or not bootloader["type"]
        ):
            raise ConfigValidationError(
                "bootloader must be an object with a non-empty type"
            )

    def _normalize_package_keys(self) -> None:
        """Collapse legacy package keys to the canonical engine contracts."""

        def package_names(*package_lists: Any) -> List[str]:
            normalized: List[str] = []
            for package_list in package_lists:
                if not isinstance(package_list, list):
                    continue
                for item in package_list:
                    name = item.get("name") if isinstance(item, dict) else item
                    if isinstance(name, str) and name and name not in normalized:
                        normalized.append(name)
            return normalized

        root_packages = package_names(
            self.master_config.get("software"),
            self.master_config.pop("packages", None),
        )
        self.master_config["software"] = root_packages

        platform = self.master_config.setdefault("platform_specific", {})
        platform_packages = package_names(
            platform.get("packages"),
            platform.pop("software", None),
        )
        platform["packages"] = platform_packages

    def assemble(
        self,
        target_arch: str,
        target_desktop: Optional[str] = None,
        target_kernel: Optional[str] = None,
        target_bootloader: Optional[str] = None,
        package_profiles: Optional[List[str]] = None,
        service_profiles: Optional[List[str]] = None,
        target_live_profile: Optional[str] = None,
        live_user: Optional[str] = None,
        live_groups: Optional[List[str]] = None,
    ) -> Config:
        """
        Configuration assembly process:
        1. Load the global manifest (global_build.json).
        2. Load the architecture-specific configuration.
        3. Load the requested desktop profile.
        4. Merge everything together.
        """
        logger.info(f"Starting configuration assembly for {target_arch}...")

        # 1. Global manifest
        global_path = self.manifest_path
        if not global_path.exists():
            raise ConfigValidationError(f"Global manifest not found at {global_path}")

        self.master_config = self._load_json_file(global_path)

        # 2. Architecture (for example: configs/architectures/x86_64.json)
        # Note: global_build may embed config data or point to an external file.
        arch_config_path = self.config_root / "architectures" / f"{target_arch}.json"
        if not arch_config_path.exists():
            raise ConfigValidationError(
                f"Architecture profile not found: {arch_config_path}"
            )
        arch_data = self._load_json_file(arch_config_path)
        self._deep_merge(self.master_config, arch_data)

        # 3. Desktop profile (if requested)
        if target_desktop:
            desktop_path = self.config_root / "desktops" / f"{target_desktop}.json"
            if desktop_path.exists():
                desktop_data = self._load_json_file(desktop_path)
                self._deep_merge(self.master_config, desktop_data)
                self.master_config["desktop"] = target_desktop
            else:
                raise ConfigValidationError(
                    f"Desktop profile not found: {desktop_path}"
                )

        # 4. Optional profile selections
        if target_kernel:
            kernel_data = self._load_optional_profile(
                "system", target_kernel, required=True
            )
            if kernel_data:
                self._deep_merge(self.master_config, kernel_data)

        if target_bootloader:
            if isinstance(target_bootloader, dict):
                self._deep_merge(self.master_config, {"bootloader": target_bootloader})
            else:
                bootloader_data = self._load_optional_profile(
                    "boot", target_bootloader, required=True
                )
                if bootloader_data:
                    self._deep_merge(self.master_config, bootloader_data)
                self.master_config["bootloader"] = {"type": target_bootloader}

        # Always load the base package profile as it is common to all builds.
        base_package_data = self._load_optional_profile("software", "base")
        if base_package_data:
            self._deep_merge(self.master_config, base_package_data)
            for pkg in self._packages(base_package_data):
                self.master_config.setdefault("software", [])
                if pkg not in self.master_config["software"]:
                    self.master_config["software"].append(pkg)

        for profile_name in package_profiles or []:
            if profile_name == "base":
                continue
            package_data = self._load_optional_profile(
                "software", profile_name, required=True
            )
            if package_data:
                self._deep_merge(self.master_config, package_data)
                for pkg in self._packages(package_data):
                    self.master_config.setdefault("software", [])
                    if pkg not in self.master_config["software"]:
                        self.master_config["software"].append(pkg)

        # Apply this after every package profile so no later merge can restore
        # a different kernel package.
        if target_kernel:
            self._apply_kernel_override(target_kernel)

        for profile_name in service_profiles or []:
            services_data = self._load_optional_profile(
                "services", profile_name, required=True
            )
            if services_data:
                self._deep_merge(self.master_config, services_data)

        if target_live_profile:
            live_profile_data = self._load_optional_profile(
                "live-users", target_live_profile, required=True
            )
            if live_profile_data:
                self._deep_merge(self.master_config, live_profile_data)

        if live_user:
            self._apply_live_user_override(live_user, live_groups)
        elif target_live_profile:
            profile_user = self._resolve_live_user_from_config()
            if isinstance(profile_user, dict):
                resolved_name = profile_user.get("name")
                if resolved_name:
                    resolved_groups = profile_user.get("groups")
                    if not isinstance(resolved_groups, list):
                        resolved_groups = None
                    self._apply_live_user_override(str(resolved_name), resolved_groups)

        # 4b. Initramfs profile (for live ISO kernel hooks)
        initramfs_profile = self._load_optional_profile("initramfs", "live")
        if initramfs_profile:
            self._deep_merge(self.master_config, initramfs_profile)

        self._normalize_package_keys()
        self._validate_assembled(target_arch)
        logger.info("Configuration assembly completed successfully.")
        return Config(self.master_config)


# Keep the legacy interface for compatibility, but delegate to the assembler.
class ConfigLoader:
    def __init__(self, config_root: Optional[str] = None):
        self.config_root = str(resolve_from_project(config_root or "configs"))
        self.assembler = ConfigAssembler(self.config_root)

    def load_arch_config(self, global_path: str, arch: str) -> Optional[Dict[str, Any]]:
        try:
            # The assembler needs the config root to load the remaining components.
            assembler = ConfigAssembler(str(resolve_from_project(global_path)))
            config_obj = assembler.assemble(arch)
            return config_obj.to_dict()
        except Exception as e:
            logger.error(f"ConfigLoader error: {e}")
            return None
