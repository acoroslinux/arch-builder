"""
Syslinux Bootloader Configurator
================================
Generates the /boot/syslinux/ configuration required for the ISO
to boot in legacy BIOS mode, matching the archiso official layout.
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from core.path_utils import resolve_from_project

logger = logging.getLogger("SyslinuxBootloader")


class SyslinuxBootloaderError(Exception):
    pass


class SyslinuxBootloader:
    def __init__(self, config: Any):
        self.config = config

    def _cfg_get(self, key: str, default: Any = None) -> Any:
        """
        Custom getter supporting dot-notation for nested dictionary lookups.
        Fixes lookup failures for keys like 'system.iso_label'.
        """
        if not self.config:
            return default

        try:
            if "." in key:
                parts = key.split(".")
                current = self.config
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return default
                return current if current is not None else default

            value = self.config.get(key, default)
            return default if value is None else value
        except Exception:
            return default

    def _build_replacements(self, iso_uuid: str = "") -> dict:
        """Build the placeholder replacement mapping from config."""
        kernel_file = self._cfg_get("platform_specific.base_kernel", "vmlinuz-linux")
        initramfs_file = self._cfg_get(
            "platform_specific.initramfs", "initramfs-linux.img"
        )
        iso_label = self._cfg_get("system.iso_label", "ARCH-MODERN")
        arch = self._cfg_get("platform_specific.architecture", "x86_64")

        kernel_params = self._cfg_get(
            "boot.kernel_params",
            "loglevel=4 quiet nouveau.modeset=1 radeon.modeset=1 i915.modeset=1 nvme_load=yes"
        )
        # Remove splash parameter for legacy BIOS boot to avoid black screen freezes
        bios_params = " ".join([p for p in kernel_params.split() if p != "splash"])
        cmdline = f"{bios_params} rw systemd.setenv=SYSTEMD_SULOGIN_FORCE=1"

        return {
            "@@BOOT_TITLE@@": "Arch Modern",
            "@@ARCH@@": arch,
            "@@KERNEL_FILE@@": kernel_file,
            "@@INITRAMFS_FILE@@": initramfs_file,
            "@@ISO_LABEL@@": iso_label,
            "@@ARCHISO_UUID@@": iso_uuid or iso_label,
            "@@BOOT_CMDLINE@@": cmdline,
            "@@INSTALL_DIR@@": "arch",
        }

    def prepare_files(self, workdir: Path, iso_uuid: str = "") -> bool:
        """Prepare BIOS boot files in /boot/syslinux/ (archiso official layout)."""
        logger.info("[SYSLINUX] Preparing legacy BIOS boot files...")

        syslinux_dir = workdir / "boot" / "syslinux"
        syslinux_dir.mkdir(parents=True, exist_ok=True)

        templates_dir = resolve_from_project("configs/templates/syslinux")
        if not templates_dir.exists():
            logger.error(f"[SYSLINUX] Templates directory not found: {templates_dir}")
            return False

        replacements = self._build_replacements(iso_uuid=iso_uuid)

        # Process all syslinux template files
        for tmpl_file in sorted(templates_dir.iterdir()):
            # Skip non-config files (e.g. .png)
            if tmpl_file.suffix == ".png":
                continue

            if tmpl_file.name.endswith(".cfg.in"):
                # Template file: apply placeholder substitutions, output without .in
                dest_name = tmpl_file.name[:-3]  # strip .in
                content = tmpl_file.read_text()
                for placeholder, value in replacements.items():
                    content = content.replace(placeholder, value)
                (syslinux_dir / dest_name).write_text(content)
                logger.info(f"[SYSLINUX] Generated {dest_name} from template")
            elif tmpl_file.suffix == ".cfg":
                # Static config file: copy directly without modifications
                shutil.copy2(tmpl_file, syslinux_dir / tmpl_file.name)
                logger.info(f"[SYSLINUX] Copied {tmpl_file.name}")

        logger.info(f"[SYSLINUX] All configs written to {syslinux_dir}")
        return True

    def generate_boot_image(self, workdir: Path, chroot_path: Path) -> bool:
        """
        Copy the binary files required by ISOLINUX from the chroot environment
        into the ISO /boot/syslinux/ directory (archiso official layout).
        """
        logger.info("[SYSLINUX] Gathering BIOS boot binaries...")
        syslinux_dir = workdir / "boot" / "syslinux"
        syslinux_dir.mkdir(parents=True, exist_ok=True)

        if chroot_path and chroot_path.exists():
            # In a real scenario, the syslinux package is installed in the chroot.
            syslinux_lib = chroot_path / "usr/lib/syslinux/bios"
            if syslinux_lib.exists():
                binaries = [
                    "isolinux.bin",
                    "ldlinux.c32",
                    "vesamenu.c32",
                    "libcom32.c32",
                    "libutil.c32",
                    "reboot.c32",
                    "poweroff.c32",
                    "chain.c32",
                    "whichsys.c32",
                    "isohdpfx.bin",
                ]
                for bin_file in binaries:
                    src = syslinux_lib / bin_file
                    if src.exists():
                        shutil.copy2(src, syslinux_dir / bin_file)
            else:
                logger.warning(
                    "[SYSLINUX] /usr/lib/syslinux/bios was not found in the chroot. Simulating files instead."
                )
                self._mock_binaries(syslinux_dir)
        else:
            self._mock_binaries(syslinux_dir)

        # Always copy splash.png from templates if it exists
        splash_src = resolve_from_project("configs/templates/syslinux/splash.png")
        if splash_src.exists():
            shutil.copy2(splash_src, syslinux_dir / "splash.png")
            logger.info("[SYSLINUX] Copied splash.png to boot/syslinux directory.")
        else:
            logger.warning("[SYSLINUX] splash.png not found in templates, menu will have no background.")

        return True

    def _mock_binaries(self, syslinux_dir: Path):
        """Create placeholder files to allow ISO generation in mock mode."""
        for mock_file in [
            "isolinux.bin", "ldlinux.c32", "isohdpfx.bin",
            "vesamenu.c32", "libcom32.c32", "libutil.c32",
            "reboot.c32", "poweroff.c32", "chain.c32", "whichsys.c32",
        ]:
            (syslinux_dir / mock_file).write_bytes(b"mock")

    def validate(self, workdir: Path) -> bool:
        return (workdir / "boot" / "syslinux" / "isolinux.bin").exists()
