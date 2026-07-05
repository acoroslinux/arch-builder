"""
System Configurator - System Customization and Configuration
============================================================
Responsible for applying customization rules that include:
1. Copying files into the filesystem.
2. Running system commands (for example, systemctl enable).
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.chroot_manager import ChrootError, ChrootManager
from core.path_utils import project_root, resolve_from_base, resolve_from_project

logger = logging.getLogger("SystemConfigurator")

class ConfigError(Exception):
    """Exception raised for system configuration errors."""

    pass

class SystemAction:
    """Base class for a configuration action."""

    def execute(self, chroot: ChrootManager, source_base: Path):
        raise NotImplementedError()

class OverlayAction(SystemAction):
    """Copy a full overlay directory onto the chroot (like airootfs)."""

    def __init__(self, overlay_dir: str):
        self.overlay_dir = overlay_dir

    def execute(self, chroot: ChrootManager, source_base: Path):
        overlay_path = resolve_from_base(source_base, self.overlay_dir)
        if not overlay_path.exists():
            logger.warning(
                f"[Overlay] Overlay directory not found: {overlay_path}"
            )
            return

        logger.info(f"[Overlay] Applying overlay from {overlay_path} to rootfs...")
        if chroot.mode == "real":
            # Use cp or rsync from the toolchain to copy the overlay.
            chroot_path = chroot.chroot_path
            # To copy the directory contents, overlay_path/* would be enough,
            # but cp -a behaves poorly with an empty wildcard, so rsync or cp -aT is safer.
            try:
                # Ideally this would use shutil.copytree locally when possible,
                # or defer to the chroot manager / toolchain.
                import subprocess

                subprocess.run(
                    ["cp", "-aT", str(overlay_path), str(chroot_path)], check=True
                )
            except Exception as e:
                logger.error(f"[Overlay] Failed to copy overlay: {e}")
        else:
            logger.info(f"    [Mock] Simulated overlay: cp -aT {overlay_path} /")

class FileAction(SystemAction):
    """Copy one file from a source path to a destination inside the chroot."""

    def __init__(self, src: str, dest: str, mode: Optional[str] = None):
        self.src = src
        self.dest = dest
        self.mode = mode

    def execute(self, chroot: ChrootManager, source_base: Path):
        src_full = resolve_from_base(source_base, self.src)
        dest_full = Path(self.dest)

        if not src_full.exists():
            logger.error(f"[Config] Source not found: {src_full}")
            return

        logger.info(f"  [File] {self.src} -> {self.dest}")

        if chroot.mode == "real":
            chroot.run_command(f"mkdir -p {dest_full.parent}")
            # For scripts, avoid routing through the toolchain because files may live outside it.
            # Copy them into place and then adjust permissions.
            host_dest = chroot.chroot_path / self.dest.lstrip("/")
            host_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_full, host_dest)

            if self.mode:
                chroot.run_command(f"chmod {self.mode} {self.dest}")
        else:
            logger.info(f"    [Mock] Virtual copy from {self.src} to {self.dest}")

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
                chroot.run_command(f"getent group {group} >/dev/null 2>&1 || groupadd {group}")

            groups_str = ",".join(groups)
            group_cmd = f"-G {groups_str}" if groups_str else ""

            # Create the user.
            chroot.run_command(f"useradd -m {group_cmd} -s /bin/bash {name}")

            # Set the password.
            if password:
                chroot.run_command(f"echo '{name}:{password}' | chpasswd")

            # Grant sudo privileges for users in the wheel group.
            if "wheel" in groups:
                chroot.run_command(
                    "sed -i 's/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers"
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
                chroot.run_command(f"systemctl enable {srv}")
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

        # 1. Overlay
        overlay_dir = cust_config.get("overlay_dir") or sys_config.get("overlay_dir")
        if overlay_dir:
            self.actions.append(OverlayAction(overlay_dir))

        # 2. Locale / hostname
        if cust_config:
            self.actions.append(LocaleAction(cust_config))

        # 3. Users
        users = cust_config.get("users", [])
        for u in users:
            # Unwrap Config dict instances.
            if hasattr(u, "_data"):
                u = u._data
            self.actions.append(UserAction(u))

        # 4. Services
        services = cust_config.get("services", [])
        if not services:
            # Backward compatibility.
            services = _safe_get(config, "platform_specific.services", [])
        if services:
            # List of strings.
            srv_list = [str(s) for s in services]
            self.actions.append(ServiceAction(srv_list))

        # 5. Commands (generic post-install scripts)
        commands = cust_config.get("commands", []) or sys_config.get("commands", [])
        for cmd in commands:
            self.actions.append(CommandAction(str(cmd)))

        # 6. Initramfs (mkinitcpio configuration)
        initramfs = _safe_get(config, "initramfs") or _safe_get(
            config, "platform_specific.initramfs_config"
        )
        if initramfs:
            if hasattr(initramfs, "_data"):
                initramfs = initramfs._data
            if isinstance(initramfs, dict):
                self.actions.append(MkinitcpioAction(initramfs))

        # 7. Standalone files (less common when overlay is used)
        files = cust_config.get("files", []) or sys_config.get("files", [])
        for f in files:
            if hasattr(f, "get"):
                src = f.get("src")
                dest = f.get("dest")
                mode = f.get("mode")
                if src and dest:
                    self.actions.append(FileAction(src, dest, mode))

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

        logger.info(
            f"Applying {len(self.actions)} system configuration actions..."
        )
        for action in self.actions:
            try:
                action.execute(self.chroot, source_base_dir)
            except Exception as e:
                logger.error(f"Failed to execute configuration action: {e}")

