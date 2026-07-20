"""
Chroot Setup Engine - Root Environment Initialization Logic
==========================================================
This module handles the dynamic construction and population of a chroot,
allowing components such as packages and desktop themes to be loaded
exclusively from configuration files.

It should not interact directly with ``subprocess`` for system commands,
and should instead delegate that work to external tools or manageable scripts.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List

from core.path_utils import resolve_from_project


class ChrootSetupError(Exception):
    """Specific exception for chroot configuration errors."""


class FileSystemHandler:
    """Static helper for complex file and directory operations."""

    @staticmethod
    def create_path(p: Path) -> None:
        """Ensure the path exists, creating parents when needed."""
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ChrootSetupError(f"Could not create path {p}: {e}")

    @staticmethod
    def copy_file(src: Path, dest: Path) -> None:
        """Copy a file safely."""
        try:
            shutil.copy2(src, dest)
        except IOError as e:
            raise ChrootSetupError(f"Failed to copy {src} to {dest}: {e}")

    @staticmethod
    def copy_directory(src: Path, dest: Path) -> None:
        """Copy a directory recursively, merging into destination."""
        try:
            if not src.is_dir():
                raise ChrootSetupError(f"Source is not a directory: {src}")

            for item in src.iterdir():
                target = dest / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
        except OSError as e:
            raise ChrootSetupError(f"Failed to copy directory {src} to {dest}: {e}")


class ChrootBuilder:
    """
    Engine responsible for initializing the operating system inside a chroot.
    Handles dynamic installation and custom configuration steps.
    """

    def __init__(self, base_path: Path):
        self.chroot_dir = base_path / "mnt/target"
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Prepare the base directory structure for the chroot."""
        print("[CHROOT] Setting up directory structure...")
        FileSystemHandler.create_path(self.chroot_dir / "etc")
        # Common directories expected in an Arch/Linux system.
        FileSystemHandler.create_path(self.chroot_dir / "var" / "log")
        FileSystemHandler.create_path(self.chroot_dir / "usr" / "bin")

    def install_packages(self, packages: List[str], arch: str) -> None:
        """
        Install packages dynamically using the provided configuration.
        NOTE: In a real environment this would call ``pacman -S <list>``.
        Here the success path is simulated to keep the module self-contained.
        """
        if not packages:
            print("[CHROOT] Warning: no packages were specified for installation.")
            return

        print(f"[CHROOT] Starting installation of {len(packages)} packages...")
        # Simulated package-manager call (for example, pacman).
        try:
            print(f"    [SIMULATION] Running: sudo pacman -S {' '.join(packages)}...")
            # A real implementation would invoke the package manager through a wrapper
            # that keeps the command non-interactive.
            print(
                "    [SUCCESS] Packages were simulated as installed inside the chroot."
            )
        except Exception as e:
            raise ChrootSetupError(f"Failed to install packages: {e}")

    def apply_profile_config(self, profile_name: str, config: Dict[str, Any]) -> None:
        """
        Apply the configuration of a profile (for example GNOME or i3wm).
        This handles desktop themes and related settings.
        """
        print(f"[CHROOT] Applying desktop profile: {profile_name}...")
        if not config or "desktop" not in config:
            return

        # Example of profile-driven dynamic logic.
        desktop = config["desktop"]

        if desktop.get("themes"):
            print(f"  -> Configuring required themes: {', '.join(desktop['themes'])}")
            # Logic for copying theme files (for example /usr/share/themes/<theme>).

        if desktop.get("post_install_scripts"):
            print("  -> Running post-install scripts:")
            for script in desktop["post_install_scripts"]:
                # These scripts belong to user setup logic,
                # which usually implies creating users and groups.
                print(
                    f"     - [SCRIPT] {script['command']} (Parameters: {script['params']})"
                )

    def copy_custom_files(self, file_rules: List[Dict[str, str]]) -> None:
        """
        Copy files according to rules defined in configuration.
        This replaces static ``cp A B``-style copies.
        Example rule: {"src": "source/ssh/sshd_config", "dest": "etc/ssh/sshd_config"}
        """
        print("[CHROOT] Applying dynamic file copy rules...")
        for rule in file_rules:
            src_value = rule.get("src")
            dest_value = rule.get("dest")
            copy_type = str(rule.get("type", "auto"))

            if not src_value or not dest_value:
                print("  [WARNING] Invalid copy rule: missing 'src' or 'dest'.")
                continue

            src = resolve_from_project(src_value)
            # Destination must always be relative to the chroot rootfs.
            chroot_relative_dest = Path(str(dest_value).lstrip("/"))
            dest = self.chroot_dir / chroot_relative_dest

            if not src.exists():
                print(f"  [WARNING] Source not found: {src_value}")
                continue

            try:
                if copy_type == "auto":
                    if src.is_dir():
                        copy_type = "directory"
                    elif src.is_file() or src.is_symlink():
                        copy_type = "file"
                    else:
                        print(
                            f"  [WARNING] Could not determine source type for: {src_value}"
                        )
                        continue

                if copy_type == "directory":
                    FileSystemHandler.create_path(dest)
                    FileSystemHandler.copy_directory(src, dest)
                    print(
                        f"  [COPY] Directory copied successfully from {src_value} to {dest_value}"
                    )
                elif copy_type == "file":
                    FileSystemHandler.create_path(dest.parent)
                    FileSystemHandler.copy_file(src, dest)
                    print(
                        f"  [COPY] File copied successfully from {src_value} to {dest_value}"
                    )
                else:
                    print(
                        f"  [WARNING] Invalid copy type '{copy_type}' for {src_value}"
                    )
            except ChrootSetupError as e:
                print(f"  [COPY ERROR] Failed to copy {src_value}: {e}")

    def build_chroot(
        self,
        packages_config: Dict[str, Any],
        desktop_config: Dict[str, Any],
        file_rules: List[Dict[str, str]],
        arch: str = "x86_64",
    ) -> None:
        """Main function that orchestrates the full chroot build."""
        print("=" * 60)
        print(f"[*] STARTING CHROOT BUILD IN {self.chroot_dir}")
        print("=" * 60)

        # 3. Copy custom files – ensure pacman.conf is in place first
        pacman_rule = {
            "src": "configs/custom_files/common/etc/pacman.conf",
            "dest": "/etc/pacman.conf",
            "type": "file",
        }
        # Add the rule only if the caller hasn't supplied it already
        if not any(r.get("dest") == "/etc/pacman.conf" for r in file_rules):
            file_rules.append(pacman_rule)

        self.copy_custom_files(file_rules)

        # 1. Install packages.
        self.install_packages(packages_config.get("packages"), arch)

        # 2. Apply profile configuration (desktop, and so on).
        if desktop_config:
            self.apply_profile_config("Custom", desktop_config)

        print("\n[SUCCESS] Chroot structure completed successfully.")
