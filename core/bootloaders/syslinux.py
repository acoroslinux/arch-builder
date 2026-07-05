"""
Syslinux Bootloader Configurator
================================
Generates the ISOLINUX/SYSLINUX configuration required for the ISO
to boot in legacy BIOS mode.
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

    def prepare_files(self, workdir: Path) -> bool:
        """Prepare BIOS boot files (ISOLINUX)."""
        logger.info("[SYSLINUX] Preparing legacy BIOS boot files...")

        isolinux_dir = workdir / "isolinux"
        isolinux_dir.mkdir(parents=True, exist_ok=True)

        cfg_dest = isolinux_dir / "isolinux.cfg"

        # 1. Load template
        template_path = resolve_from_project("configs/templates/syslinux/syslinux.cfg.in")
        if not template_path.exists():
            logger.error(f"[SYSLINUX] Template file not found: {template_path}")
            return False

        template_content = template_path.read_text()

        # 2. Prepare placeholder mapping using the nested dict safe getter
        kernel_file = self._cfg_get("platform_specific.base_kernel", "vmlinuz-linux")
        initramfs_file = self._cfg_get(
            "platform_specific.initramfs", "initramfs-linux.img"
        )
        iso_label = self._cfg_get("system.iso_label", "ARCH-MODERN")
        arch = self._cfg_get("platform_specific.architecture", "x86_64")
        
        # FIX: Added 'rw' and 'systemd.setenv' parameter to bypass root locking on boot failure
        cmdline = "loglevel=4 quiet rw systemd.setenv=SYSTEMD_SULOGIN_FORCE=1"
        archiso_uuid = self._cfg_get("system.iso_uuid", "ARCHISO_UUID_PLACEHOLDER")

        replacements = {
            "@@BOOT_TITLE@@": "Arch-Builder Live OS",
            "@@ARCH@@": arch,
            "@@ARCHISO_UUID@@": archiso_uuid,
            "@@KERNEL_FILE@@": kernel_file,
            "@@INITRAMFS_FILE@@": initramfs_file,
            "@@ISO_LABEL@@": iso_label,
            "@@BOOT_CMDLINE@@": cmdline,
        }

        # 3. Apply replacements
        for placeholder, value in replacements.items():
            template_content = template_content.replace(placeholder, value)

        # 4. Write final file
        cfg_dest.write_text(template_content)
        logger.info(f"[SYSLINUX] isolinux.cfg generated successfully at {cfg_dest}")

        return True

    def generate_boot_image(self, workdir: Path, chroot_path: Path) -> bool:
        """
        Copy the binary files required by ISOLINUX (isolinux.bin, ldlinux.c32,
        and others) from the chroot environment into the ISO /isolinux directory.
        """
        logger.info("[SYSLINUX] Gathering BIOS boot binaries...")
        isolinux_dir = workdir / "isolinux"

        if chroot_path and chroot_path.exists():
            # In a real scenario, the syslinux package would be installed in the chroot.
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
                ]
                for bin_file in binaries:
                    src = syslinux_lib / bin_file
                    if src.exists():
                        shutil.copy2(src, isolinux_dir / bin_file)
            else:
                logger.warning(
                    "[SYSLINUX] /usr/lib/syslinux/bios was not found in the chroot. Simulating files instead."
                )
                self._mock_binaries(isolinux_dir)
        else:
            self._mock_binaries(isolinux_dir)

        return True

    def _mock_binaries(self, isolinux_dir: Path):
        """Create placeholder files to allow ISO generation in mock mode."""
        (isolinux_dir / "isolinux.bin").write_bytes(b"mock")
        (isolinux_dir / "ldlinux.c32").write_bytes(b"mock")

    def validate(self, workdir: Path) -> bool:
        return (workdir / "isolinux" / "isolinux.cfg").exists()
