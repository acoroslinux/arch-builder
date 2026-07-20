"""
System Configurator - System Customization and Configuration
============================================================
Responsible for applying customization rules that include:
1. Copying files into the filesystem.
2. Running system commands (for example, systemctl enable).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.chroot_manager import ChrootManager
from core.path_utils import project_root, resolve_from_project

logger = logging.getLogger("SystemConfigurator")


class ConfigError(Exception):
    """Exception raised for system configuration errors."""


class SystemAction:
    """Base class for a configuration action."""

    def execute(self, chroot: ChrootManager, source_base: Path):
        raise NotImplementedError()


class CommandAction(SystemAction):
    """Execute a command directly inside the chroot."""

    def __init__(self, command: str):
        self.command = command

    def execute(self, chroot: ChrootManager, source_base: Path):
        logger.info(f"  [Cmd] Running: {self.command}")
        if chroot.mode == "real":
            # Use bash instead of sh for compatibility with isolated bootstrap
            chroot.run_command(f"bash -lc '{self.command}'")
        else:
            logger.info(f"    [Mock] Simulated command: {self.command}")


class UserAction(SystemAction):
    """Create users and apply their related settings."""

    def __init__(self, user_config: Dict[str, Any]):
        self.user_config = user_config

    def execute(self, chroot: ChrootManager, source_base: Path):
        name = self.user_config.get("name")
        if not name:
            return

        groups = self.user_config.get("groups", [])
        password = self.user_config.get("password", "")

        logger.info(f"  [User] Creating user: {name}")

        if chroot.mode == "real":
            # Create groups if needed. groupadd can handle some cases, but we keep it simple.
            for group in groups:
                chroot.run_command(
                    f"getent group {group} >/dev/null 2>&1 || groupadd {group}"
                )

            groups_str = ",".join(groups)

            # Create the user if not exists, otherwise update groups
            chroot.run_command(
                f"id -u {name} >/dev/null 2>&1 || useradd -m -s /bin/bash {name}"
            )
            if groups_str:
                chroot.run_command(f"usermod -G {groups_str} {name}")

            # Ensure home directory exists and has correct ownership
            chroot.run_command(f"mkdir -p /home/{name}")
            chroot.run_command(f"chown -R {name}:{name} /home/{name}")

            # Set the password.
            if password:
                chroot.run_command(f"echo '{name}:{password}' | chpasswd")

            # Grant sudo privileges for users in the wheel group.
            if "wheel" in groups:
                chroot.run_command(
                    "mkdir -p /etc/sudoers.d && echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/10-wheel"
                )
        else:
            logger.info(f"    [Mock] Create user: {name} (groups: {groups})")


class ServiceAction(SystemAction):
    """Enable systemd services."""

    def __init__(self, services: List[str]):
        self.services = services

    def execute(self, chroot: ChrootManager, source_base: Path):
        for srv in self.services:
            logger.info(f"  [Service] Enable {srv}")
            if chroot.mode == "real":
                try:
                    chroot.run_command(f"systemctl enable {srv}")
                except Exception as e:
                    logger.warning(
                        f"  [Service] Could not enable {srv}: {e}. "
                        f"Service may not be installed or available."
                    )
            else:
                logger.info(f"    [Mock] systemctl enable {srv}")


class MkinitcpioAction(SystemAction):
    """Configure initramfs generation through mkinitcpio."""

    def __init__(self, initramfs_config: Dict[str, Any]):
        self.modules = initramfs_config.get("modules", [])
        self.binaries = initramfs_config.get("binaries", [])
        self.files = initramfs_config.get("files", [])
        self.hooks = initramfs_config.get("hooks", [])

    def execute(self, chroot: ChrootManager, source_base: Path):
        if not any([self.modules, self.binaries, self.files, self.hooks]):
            return

        logger.info(
            "  [Initramfs] Configuring /etc/mkinitcpio.conf for Live ISO mode..."
        )
        conf_content = (
            f"MODULES=({' '.join(self.modules)})\n"
            f"BINARIES=({' '.join(self.binaries)})\n"
            f"FILES=({' '.join(self.files)})\n"
            f"HOOKS=({' '.join(self.hooks)})\n"
        )

        if chroot.mode == "real":
            target_conf = chroot.chroot_path / "etc" / "mkinitcpio.conf"
            target_conf.parent.mkdir(parents=True, exist_ok=True)
            target_conf.write_text(conf_content)
        else:
            logger.info(
                f"    [Mock] mkinitcpio.conf generated (hooks: {', '.join(self.hooks)})"
            )


class LocaleAction(SystemAction):
    """Configure locales, timezone, hostname, and keymap."""

    def __init__(self, config: Dict[str, Any]):
        self.hostname = config.get("hostname", "arch-builder")
        self.timezone = config.get("timezone", "UTC")
        self.locale = config.get("locale", "en_US.UTF-8")
        self.keymap = config.get("keymap", "us")

    def execute(self, chroot: ChrootManager, source_base: Path):
        logger.info(
            f"  [Locale] Hostname: {self.hostname}, Timezone: {self.timezone}, Locale: {self.locale}"
        )
        if chroot.mode == "real":
            chroot.run_command(f"echo {self.hostname} > /etc/hostname")
            chroot.run_command(
                f"ln -sf /usr/share/zoneinfo/{self.timezone} /etc/localtime"
            )

            # Locales
            chroot.run_command(
                f"sed -i 's/^#{self.locale}/{self.locale}/' /etc/locale.gen"
            )
            chroot.run_command("locale-gen")
            chroot.run_command(f"echo 'LANG={self.locale}' > /etc/locale.conf")

            # Vconsole / keymap
            chroot.run_command(f"echo 'KEYMAP={self.keymap}' > /etc/vconsole.conf")
        else:
            logger.info("    [Mock] Apply locale/timezone/hostname")


class StructuredCopyAction(SystemAction):
    """Configures structured copy of files from custom_files to rootfs."""

    def __init__(
        self,
        customizations_path: str,
        copy_files_list: List[Dict[str, str]],
        architecture: str,
    ):
        self.customizations_path = Path(customizations_path)
        self.copy_files_list = copy_files_list
        self.architecture = architecture

    def execute(self, chroot: ChrootManager, source_base: Path):
        logger.info(
            f"  [StructuredCopy] Copying {len(self.copy_files_list)} structured files to rootfs..."
        )

        is_arm = self.architecture.startswith(("aarch64", "arm"))

        # Resolve python version in chroot if {python_version} is present in destinations
        py_ver = "3.12"
        if chroot.mode == "real":
            python_dirs = list(chroot.chroot_path.glob("usr/lib/python3.*"))
            if python_dirs:
                py_ver = python_dirs[0].name.replace("python", "")

        for entry in self.copy_files_list:
            src_rel = entry.get("source")
            dest_rel = entry.get("destination")
            if not src_rel or not dest_rel:
                continue

            # Apply conditional architecture filters as described in the comments
            if is_arm:
                if "grub/themes" in src_rel:
                    logger.info(
                        f"  [StructuredCopy] Skipping {src_rel} (not copied on ARM architecture)"
                    )
                    continue

            # Format destinations that contain python_version
            dest_rel = dest_rel.format(python_version=py_ver)

            src_path = source_base / self.customizations_path / src_rel
            dest_path = chroot.chroot_path / dest_rel.lstrip("/")

            logger.info(f"  [StructuredCopy] Copying: {src_rel} -> {dest_rel}")

            if chroot.mode == "real":
                if not src_path.exists():
                    logger.warning(
                        f"  [StructuredCopy] Source path does not exist: {src_path}"
                    )
                    continue

                import os
                import subprocess

                # Ensure destination parent directory exists
                dest_dir = (
                    dest_path
                    if src_path.is_dir() and not dest_rel.endswith(src_path.name)
                    else dest_path.parent
                )
                dest_dir_in_chroot = Path("/") / dest_dir.relative_to(
                    chroot.chroot_path
                )

                chroot.run_command(f"mkdir -p {dest_dir_in_chroot}")

                # Copy file/directory preserving all attributes except ownership and merging contents (-T)
                cmd_copy = [
                    "cp",
                    "-a",
                    "--no-preserve=ownership",
                    "-T",
                    str(src_path),
                    str(dest_path),
                ]
                try:
                    if os.geteuid() != 0:
                        subprocess.run(["sudo"] + cmd_copy, check=True)
                    else:
                        subprocess.run(cmd_copy, check=True)
                except Exception as e:
                    logger.error(
                        f"  [StructuredCopy] Failed to copy {src_path} to {dest_path}: {e}"
                    )
            else:
                logger.info(f"    [Mock] Copy {src_path} to {dest_path}")


class SystemConfigurator:
    """
    The configurator is the system customization coordinator.
    It processes configuration "customizations" and applies them to the environment.
    """

    def __init__(self, chroot: Optional[ChrootManager] = None):
        self.chroot = chroot
        self.actions: List[SystemAction] = []

    def load_from_config(self, config: Any):
        """
        Load actions from the Config object, which already contains merged data
        from global_build.json, architecture.json, and other sources.
        """

        # Retrieve the customization block.
        # It may live under system_config or customizations.
        def _safe_get(cfg: Any, key: str, default: Any = None) -> Any:
            if not hasattr(cfg, "get"):
                return default
            try:
                value = cfg.get(key, default)
            except TypeError:
                # Compatibility with legacy/mocked configs exposing get(key) only.
                value = cfg.get(key)
            return default if value is None else value

        if hasattr(config, "get"):
            cust_config = _safe_get(config, "customizations", {})
            sys_config = _safe_get(config, "system_config", {})
        else:
            return

        # 3. Locale / hostname
        if cust_config:
            self.actions.append(LocaleAction(cust_config))

        # 4. Users
        users = cust_config.get("users", [])
        for u in users:
            # Unwrap Config dict instances.
            if hasattr(u, "_data"):
                u = u._data
            self.actions.append(UserAction(u))

        # 5. Services
        services = cust_config.get("services", [])
        if not services:
            # Backward compatibility.
            services = _safe_get(config, "platform_specific.services", [])
        if services:
            # List of strings.
            srv_list = [str(s) for s in services]
            self.actions.append(ServiceAction(srv_list))

        # 6. Commands (generic post-install scripts)
        commands = cust_config.get("commands", []) or sys_config.get("commands", [])
        for cmd in commands:
            self.actions.append(CommandAction(str(cmd)))

        # 7. Initramfs (mkinitcpio configuration)
        initramfs = (
            _safe_get(config, "initramfs_config")
            or _safe_get(config, "initramfs")
            or _safe_get(config, "platform_specific.initramfs_config")
        )
        if initramfs:
            if hasattr(initramfs, "_data"):
                initramfs = initramfs._data
            if isinstance(initramfs, dict):
                self.actions.append(MkinitcpioAction(initramfs))

        # 8. Structured Copy (Desktop-environment file copying)
        desktop_env = _safe_get(config, "desktop_environment")
        if desktop_env:
            if hasattr(desktop_env, "_data"):
                desktop_env = desktop_env._data
            if isinstance(desktop_env, dict):
                custom_path = desktop_env.get(
                    "customizations_path", "configs/custom_files/"
                )
                use_common = desktop_env.get("use_common_config", False)
                copy_files = desktop_env.get("copy_files", []) or []

                final_copy_list = []
                if use_common:
                    base_custom_path = resolve_from_project(
                        "configs/base_customizations.json"
                    )
                    if base_custom_path.exists():
                        try:
                            import json

                            with open(base_custom_path, "r", encoding="utf-8") as f:
                                base_data = json.load(f)
                            base_list = base_data.get("base_copy_files", [])
                            final_copy_list.extend(base_list)
                            logger.info(
                                f"Loaded {len(base_list)} common copy entries from base_customizations.json"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to load/parse configs/base_customizations.json: {e}"
                            )

                # Add desktop specific copy_files
                for item in copy_files:
                    if hasattr(item, "_data"):
                        item = item._data
                    if isinstance(item, dict):
                        final_copy_list.append(item)

                if final_copy_list:
                    arch = _safe_get(config, "platform_specific.architecture", "x86_64")
                    self.actions.append(
                        StructuredCopyAction(custom_path, final_copy_list, arch)
                    )

    def apply(self, source_base_dir: Optional[Path] = None):
        """Apply all registered actions to the chroot."""
        if not self.chroot:
            logger.warning(
                "Configurator called without a ChrootManager. No action was performed."
            )
            return

        source_base_dir = resolve_from_project(source_base_dir or project_root())

        if not self.actions:
            logger.info("No pending system configuration actions to apply.")
            return

        logger.info(f"Applying {len(self.actions)} system configuration actions...")
        for action in self.actions:
            try:
                action.execute(self.chroot, source_base_dir)
            except Exception as e:
                logger.error(f"Failed to execute configuration action: {e}")
