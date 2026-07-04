import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.path_utils import resolve_from_project

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConfigLoader")


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""

    pass


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
        self.config_root = resolve_from_project(config_root)
        self.master_config: Dict[str, Any] = {}

    def _deep_merge(
        self, base: Dict[str, Any], update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge two dictionaries and combine lists without losing data."""
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key] = self._deep_merge(base[key], value)
            elif (
                isinstance(value, list) and key in base and isinstance(base[key], list)
            ):
                # Extend lists while avoiding duplicates where simple checks work.
                for item in value:
                    if item not in base[key]:
                        base[key].append(item)
            else:
                base[key] = value
        return base

    def _load_json_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            return {}

    def _load_optional_profile(self, category: str, profile_name: str) -> Dict[str, Any]:
        """Load a profile JSON from configs/<category>/<profile_name>.json if it exists."""
        profile_path = self.config_root / category / f"{profile_name}.json"
        if not profile_path.exists():
            logger.warning(
                f"Profile '{profile_name}' not found in '{category}' at {profile_path}"
            )
            return {}
        return self._load_json_file(profile_path)

    def _apply_kernel_override(self, kernel_name: str) -> None:
        """Set selected kernel and align related fields in platform_specific."""
        platform = self.master_config.setdefault("platform_specific", {})
        # Convert kernel package name to kernel filename (e.g., "linux" -> "vmlinuz-linux")
        base_kernel = kernel_name if kernel_name.startswith("vmlinuz-") else f"vmlinuz-{kernel_name}"
        platform["base_kernel"] = base_kernel

        # Keep initramfs naming coherent with selected kernel.
        platform["initramfs"] = f"initramfs-{kernel_name}.img"

        kernel_candidates = {"linux", "linux-lts", "linux-zen", "linux-hardened"}
        packages = platform.get("packages")
        if not isinstance(packages, list):
            return

        replaced = False
        for idx, item in enumerate(packages):
            if isinstance(item, dict):
                name = item.get("name")
                if name in kernel_candidates:
                    packages[idx] = {"name": kernel_name}
                    replaced = True
            elif isinstance(item, str) and item in kernel_candidates:
                packages[idx] = kernel_name
                replaced = True

        if not replaced:
            packages.append({"name": kernel_name})

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
        global_path = self.config_root / "global_build.json"
        if not global_path.exists():
            raise ConfigValidationError(
                f"Global manifest not found at {global_path}"
            )

        self.master_config = self._load_json_file(global_path)

        # 2. Architecture (for example: configs/architectures/x86_64.json)
        # Note: global_build may embed config data or point to an external file.
        arch_config_path = self.config_root / "architectures" / f"{target_arch}.json"
        if arch_config_path.exists():
            arch_data = self._load_json_file(arch_config_path)
            self._deep_merge(self.master_config, arch_data)
        else:
            logger.warning(
                f"No architecture-specific file found at {arch_config_path}"
            )

        # 3. Desktop profile (if requested)
        if target_desktop:
            desktop_path = self.config_root / "desktops" / f"{target_desktop}.json"
            if desktop_path.exists():
                desktop_data = self._load_json_file(desktop_path)
                self._deep_merge(self.master_config, desktop_data)
            else:
                logger.warning(
                    f"Desktop '{target_desktop}' not found at {desktop_path}"
                )

        # 4. Optional profile selections
        if target_kernel:
            kernel_data = self._load_optional_profile("kernels", target_kernel)
            if kernel_data:
                self._deep_merge(self.master_config, kernel_data)
            self._apply_kernel_override(target_kernel)

        if target_bootloader:
            bootloader_data = self._load_optional_profile("bootloaders", target_bootloader)
            if bootloader_data:
                self._deep_merge(self.master_config, bootloader_data)

        for profile_name in package_profiles or []:
            package_data = self._load_optional_profile("packages", profile_name)
            if package_data:
                self._deep_merge(self.master_config, package_data)

        for profile_name in service_profiles or []:
            services_data = self._load_optional_profile("services", profile_name)
            if services_data:
                self._deep_merge(self.master_config, services_data)

        if target_live_profile:
            live_profile_data = self._load_optional_profile("live-users", target_live_profile)
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

        # 5. Additional components (bootloaders, etc.)
        # The global "components" section can be used to discover extra modules.
        components = self.master_config.get("components", {})
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict) and comp_data.get("type") == "module_binary":
                # Placeholder for loading binary bootloader modules if needed.
                pass
            elif isinstance(comp_data, list):
                for item in comp_data:
                    if isinstance(item, dict) and item.get("type") == "module_binary":
                        pass

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
            assembler = ConfigAssembler(str(resolve_from_project(global_path).parent))
            config_obj = assembler.assemble(arch)
            return config_obj.to_dict()
        except Exception as e:
            logger.error(f"ConfigLoader error: {e}")
            return None
