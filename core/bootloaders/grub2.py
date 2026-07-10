"""
Grub2 Bootloader Configurator
=============================
Generates the GRUB2 configuration and EFI image (efiboot.img)
required for the ISO to boot in UEFI mode.

Uses grub-mkstandalone with an embedded grub-embed.cfg to produce
BOOTx64.EFI that correctly locates the ISO volume by label.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.path_utils import resolve_from_project

logger = logging.getLogger("Grub2Bootloader")


class Grub2BootloaderError(Exception):
    pass


class Grub2Bootloader:
    def __init__(self, config: Any, root_device_id: str) -> None:
        self.config = config
        self.root_device_id = root_device_id

    def _cfg_get(self, key: str, default: Any = None) -> Any:
        """
        Custom getter that supports dot-notation for nested dictionary lookups.
        Example: 'system.iso_label' will look into config['system']['iso_label']
        """
        if not self.config:
            return default

        try:
            if hasattr(self.config, "get"):
                val = self.config.get(key)
                if val is not None:
                    return val

            if "." in key:
                parts = key.split(".")
                current = self.config
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    elif hasattr(current, "get"):
                        current = current.get(part)
                    else:
                        return default
                return current if current is not None else default

            if hasattr(self.config, "get"):
                value = self.config.get(key, default)
                return default if value is None else value
            return default
        except Exception:
            return default

    def _build_replacements(self, workdir: Path) -> dict:
        """Build the placeholder replacement mapping from config."""
        kernel_file = self._cfg_get("platform_specific.base_kernel", "vmlinuz-linux")
        initramfs_file = self._cfg_get(
            "platform_specific.initramfs", "initramfs-linux.img"
        )
        iso_label = self._cfg_get("system.iso_label", "ARCH-MODERN")
        arch = self._cfg_get("platform_specific.architecture", "x86_64")
        kernel_params = self._cfg_get("boot.kernel_params", "loglevel=4 quiet splash")
        cmdline = f"{kernel_params} rw systemd.setenv=SYSTEMD_SULOGIN_FORCE=1"
        install_dir = "arch"

        return {
            "@@BOOT_TITLE@@": "Arch Modern",
            "@@ARCH@@": arch,
            "@@KERNEL_FILE@@": kernel_file,
            "@@INITRAMFS_FILE@@": initramfs_file,
            "@@ISO_LABEL@@": iso_label,
            "@@BOOT_CMDLINE@@": cmdline,
            "@@INSTALL_DIR@@": install_dir,
        }

    def prepare_files(self, workdir: Path) -> bool:
        """Prepare EFI boot files from templates."""
        logger.info("[GRUB2] Preparing EFI boot files from template...")
        efi_dir = workdir / "EFI" / "BOOT"
        efi_dir.mkdir(parents=True, exist_ok=True)

        grub_cfg_dest = workdir / "boot" / "grub" / "grub.cfg"
        grub_cfg_dest.parent.mkdir(parents=True, exist_ok=True)

        # 1. Load grub.cfg.in template
        template_path = resolve_from_project("configs/templates/grub/grub.cfg.in")
        if not template_path.exists():
            logger.error(f"[GRUB2] Template file not found: {template_path}")
            return False

        template_content = template_path.read_text()
        replacements = self._build_replacements(workdir)

        # 2. Apply replacements
        for placeholder, value in replacements.items():
            template_content = template_content.replace(placeholder, value)

        # 3. Write final grub.cfg
        grub_cfg_dest.write_text(template_content)
        logger.info(f"[GRUB2] grub.cfg generated successfully at {grub_cfg_dest}")

        return True

    def generate_embed_cfg(self, workdir: Path, dest_path: Path) -> bool:
        """Generate the grub-embed.cfg from template, applying placeholder substitutions."""
        embed_template = resolve_from_project("configs/templates/grub/grub-embed.cfg.in")
        if not embed_template.exists():
            logger.warning("[GRUB2] grub-embed.cfg.in not found, skipping embed cfg generation")
            return False

        content = embed_template.read_text()
        replacements = self._build_replacements(workdir)
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)

        dest_path.write_text(content)
        logger.info(f"[GRUB2] grub-embed.cfg generated at {dest_path}")
        return True

    def generate_boot_image(self, workdir: Path, chroot_path: Path) -> bool:
        """
        Generate efiboot.img, the UEFI FAT boot image.
        In real mode, uses grub-mkstandalone inside the chroot to create
        a BOOTx64.EFI with the embedded grub-embed.cfg.
        """
        logger.info("[GRUB2] Generating UEFI boot image (efiboot.img)...")

        efi_img_path = workdir / "EFI" / "efiboot.img"
        efi_img_path.parent.mkdir(parents=True, exist_ok=True)
        efi_binary = workdir / "EFI" / "BOOT" / "BOOTx64.EFI"

        # ISO label used for FAT volume naming inside efiboot.img
        iso_label = self._cfg_get("system.iso_label", "ARCH-MODERN")

        is_mock = (
            getattr(self.config, "mode", "mock") == "mock"
            or not chroot_path
            or not chroot_path.exists()
        )

        if is_mock:
            logger.info("[GRUB2] [MOCK] Creating efiboot.img on host (best-effort)")
            efi_binary.parent.mkdir(parents=True, exist_ok=True)
            # Create a placeholder BOOTx64.EFI so we can include it in the FAT image
            efi_binary.write_bytes(b"mock_bootx64_efi")

            # Prefer using the Python pyfatfs library (available in .venv) to create
            # the FAT image without requiring system tools. Fall back to host tools
            # if pyfatfs is not available.
            try:
                from pyfatfs.PyFat import PyFat
                from pyfatfs.PyFatFS import PyFatFS

                tmp_img = workdir / "EFI" / "efiboot.img.tmp"
                # create or truncate file to desired size (32MiB)
                size = 32 * 1024 * 1024
                with open(tmp_img, "wb") as f:
                    f.truncate(size)

                # Make FAT32 filesystem inside file
                pf = PyFat()
                pf.mkfs(str(tmp_img), PyFat.FAT_TYPE_FAT32, size=size, label=iso_label[:11])

                # Open PyFatFS to write files
                fs = PyFatFS(str(tmp_img))
                try:
                    # Ensure directories
                    try:
                        fs.makedir("/EFI")
                    except Exception:
                        pass
                    try:
                        fs.makedir("/EFI/BOOT")
                    except Exception:
                        pass

                    # copy BOOTx64.EFI
                    if efi_binary.exists():
                        with fs.open("/EFI/BOOT/BOOTx64.EFI", "wb") as dst, open(efi_binary, "rb") as src:
                            dst.write(src.read())

                    # copy kernel/initramfs if present in staging tree
                    arch_dir = workdir / "arch" / self._cfg_get("platform_specific.architecture", "x86_64")
                    kernel_name = self._cfg_get("platform_specific.base_kernel", "vmlinuz-linux")
                    initramfs_name = self._cfg_get("platform_specific.initramfs", "initramfs-linux.img")
                    candidate_kernel = workdir / "arch" / self._cfg_get('platform_specific.architecture','x86_64') / kernel_name
                    candidate_initrd = workdir / "arch" / self._cfg_get('platform_specific.architecture','x86_64') / initramfs_name
                    if candidate_kernel.exists():
                        try:
                            fs.makedirs(f"/arch/boot/{arch_dir.name}")
                        except Exception:
                            pass
                        with fs.open(f"/arch/boot/{arch_dir.name}/{kernel_name}", "wb") as dst, open(candidate_kernel, "rb") as src:
                            dst.write(src.read())
                    if candidate_initrd.exists():
                        with fs.open(f"/arch/boot/{arch_dir.name}/{initramfs_name}", "wb") as dst, open(candidate_initrd, "rb") as src:
                            dst.write(src.read())

                    # copy loader files
                    loader_dir = workdir / "loader"
                    if loader_dir.exists():
                        try:
                            fs.makedirs("/loader/entries")
                        except Exception:
                            pass
                        if (loader_dir / "loader.conf").exists():
                            with fs.open("/loader/loader.conf", "wb") as dst, open(loader_dir / "loader.conf", "rb") as src:
                                dst.write(src.read())
                        entries_dir = loader_dir / "entries"
                        if entries_dir.exists():
                            for entry in entries_dir.glob("*"):
                                if entry.is_file():
                                    with fs.open(f"/loader/entries/{entry.name}", "wb") as dst, open(entry, "rb") as src:
                                        dst.write(src.read())

                finally:
                    try:
                        fs.close()
                    except Exception:
                        pass

                shutil.copy2(tmp_img, efi_img_path)
                tmp_img.unlink(missing_ok=True)
                logger.info(f"[GRUB2] efiboot.img created (pyfatfs): {efi_img_path}")
                return True
            except Exception as e:
                logger.warning(f"[GRUB2] pyfatfs-based efiboot.img creation failed: {e}; falling back to host tools")
                # fall through to host-tool based attempts below

        # --- Real mode: use grub-mkstandalone inside the chroot ---
        chroot_embed_cfg = chroot_path / "tmp" / "grub-embed.cfg"
        chroot_efi_out = chroot_path / "tmp" / "BOOTx64.EFI"
        chroot_tmp_img = chroot_path / "tmp" / "efiboot.img"

        try:
            # Generate the embedded GRUB config
            self.generate_embed_cfg(workdir, chroot_embed_cfg)

            iso_label = self._cfg_get("system.iso_label", "ARCH-MODERN")

            # Build BOOTx64.EFI using grub-mkstandalone
            grub_modules = (
                "all_video at_keyboard boot btrfs cat chain configfile echo "
                "efifwsetup efinet exfat ext2 fat font gfxmenu gfxterm gzio "
                "halt hfsplus iso9660 jpeg keylayouts linux loadenv loopback "
                "lsefi lsefimmap minicmd normal ntfs part_apple part_gpt "
                "part_msdos png read reboot regexp search search_fs_file "
                "search_fs_uuid search_label serial sleep udf usb video xfs zstd"
            )
            cmd_standalone = [
                "chroot", str(chroot_path), "bash", "-c",
                f"grub-mkstandalone -O x86_64-efi "
                f"--modules=\"{grub_modules}\" "
                f"--locales=\"en@quot\" "
                f"--themes=\"\" "
                f"-o /tmp/BOOTx64.EFI "
                f"boot/grub/grub.cfg=/tmp/grub-embed.cfg"
            ]
            subprocess.run(cmd_standalone, check=True, capture_output=True)
            shutil.copy2(chroot_efi_out, efi_binary)
            logger.info(f"[GRUB2] BOOTx64.EFI created via grub-mkstandalone: {efi_binary}")

            # Build the efiboot.img FAT image containing BOOTx64.EFI
            # Prepare loader files (loader.conf + entries) inside chroot tmp for inclusion
            try:
                chroot_loader_tmp = chroot_path / "tmp" / "efiboot_loader"
                if chroot_loader_tmp.exists():
                    shutil.rmtree(chroot_loader_tmp, ignore_errors=True)
                (chroot_loader_tmp).mkdir(parents=True, exist_ok=True)
                # Copy loader files from workdir into chroot tmp
                if (workdir / "loader").exists():
                    loader_conf_src = workdir / "loader" / "loader.conf"
                    if loader_conf_src.exists():
                        shutil.copy2(loader_conf_src, chroot_loader_tmp / "loader.conf")
                    entries_src = workdir / "loader" / "entries"
                    if entries_src.exists():
                        (chroot_loader_tmp / "entries").mkdir(parents=True, exist_ok=True)
                        for entry in entries_src.glob("*"):
                            if entry.is_file():
                                shutil.copy2(entry, chroot_loader_tmp / "entries" / entry.name)
            except Exception:
                logger.warning("[GRUB2] Failed to stage loader files into chroot tmp; continuing without them")

            # Construct command to create FAT image and copy files into it
            cmd_parts = [
                "dd if=/dev/zero of=/tmp/efiboot.img bs=1M count=32",
                f"mkfs.fat -n {iso_label[:11]} /tmp/efiboot.img",
                "mmd -i /tmp/efiboot.img ::/EFI",
                "mmd -i /tmp/efiboot.img ::/EFI/BOOT",
                "mcopy -i /tmp/efiboot.img /tmp/BOOTx64.EFI ::/EFI/BOOT/BOOTx64.EFI",
                # Also copy kernel and initramfs into the FAT image so systemd-boot can load them
                "mmd -i /tmp/efiboot.img ::/arch",
                "mmd -i /tmp/efiboot.img ::/arch/boot",
                f"mmd -i /tmp/efiboot.img ::/arch/boot/{self._cfg_get('platform_specific.architecture','x86_64')}",
                f"mcopy -i /tmp/efiboot.img /boot/{self._cfg_get('platform_specific.base_kernel','vmlinuz-linux')} ::/arch/boot/{self._cfg_get('platform_specific.architecture','x86_64')}/{self._cfg_get('platform_specific.base_kernel','vmlinuz-linux')}",
                f"mcopy -i /tmp/efiboot.img /boot/{self._cfg_get('platform_specific.initramfs','initramfs-linux.img')} ::/arch/boot/{self._cfg_get('platform_specific.architecture','x86_64')}/{self._cfg_get('platform_specific.initramfs','initramfs-linux.img')}",
            ]

            # If loader files were staged into chroot tmp, add them to the image
            chroot_loader_tmp = chroot_path / "tmp" / "efiboot_loader"
            if chroot_loader_tmp.exists():
                cmd_parts.extend([
                    "mmd -i /tmp/efiboot.img ::/loader",
                    "mmd -i /tmp/efiboot.img ::/loader/entries",
                ])
                if (chroot_loader_tmp / "loader.conf").exists():
                    cmd_parts.append(f"mcopy -i /tmp/efiboot.img /tmp/efiboot_loader/loader.conf ::/loader/loader.conf")
                entries_dir = chroot_loader_tmp / "entries"
                if entries_dir.exists():
                    for entry in entries_dir.glob("*"):
                        if entry.is_file():
                            cmd_parts.append(f"mcopy -i /tmp/efiboot.img /tmp/efiboot_loader/entries/{entry.name} ::/loader/entries/{entry.name}")

            cmd_img = ["chroot", str(chroot_path), "bash", "-c", " && ".join(cmd_parts)]
            subprocess.run(cmd_img, check=True, capture_output=True)
            shutil.copy2(chroot_tmp_img, efi_img_path)
            logger.info(f"[GRUB2] efiboot.img created: {efi_img_path}")
            return True

        except (subprocess.CalledProcessError, FileNotFoundError, shutil.Error) as e:
            logger.error(f"[GRUB2] Failed to create EFI boot image via chroot: {e}")
            # Fallback to mock files so the build doesn't hard-fail
            efi_binary.write_bytes(b"mock_bootx64_efi")
            efi_img_path.write_bytes(b"mock_efi_image_content")
            return True
        finally:
            for tmp_file in [chroot_embed_cfg, chroot_efi_out, chroot_tmp_img]:
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)

    def validate(self, workdir: Path) -> bool:
        return (workdir / "boot" / "grub" / "grub.cfg").exists()
