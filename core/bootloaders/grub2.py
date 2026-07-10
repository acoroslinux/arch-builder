"""
Grub2 Bootloader Configurator
=============================
Generates the GRUB2 configuration and EFI image (efiboot.img)
required for the ISO to boot in UEFI mode.

Uses grub-mkstandalone with an embedded grub-embed.cfg to produce
BOOTx64.EFI that correctly locates the ISO volume by searching for
the UUID marker file /boot/<iso_uuid>.uuid on all block devices.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.path_utils import resolve_from_project

logger = logging.getLogger("Grub2Bootloader")


class Grub2BootloaderError(Exception):
    pass


class Grub2Bootloader:
    def __init__(self, config: Any, root_device_id: str, iso_uuid: str = "") -> None:
        self.config = config
        self.root_device_id = root_device_id
        self.iso_uuid = iso_uuid

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
            "@@ARCHISO_UUID@@": self.iso_uuid or iso_label,
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

    def generate_boot_image(self, workdir: Path, chroot_path: Path = None) -> bool:
        """
        Generate efiboot.img — the FAT EFI System Partition image appended to the ISO.

        All tools (grub-mkstandalone, mkfs.fat, mmd, mcopy) run inside the isolated
        Arch chroot where dosfstools, mtools and grub are installed.

        Required packages inside the chroot (filesystems.json):
          dosfstools  → mkfs.fat
          mtools      → mmd, mcopy
          grub        → grub-mkstandalone

        The resulting efiboot.img contains:
          /EFI/BOOT/BOOTx64.EFI             — GRUB EFI binary with embedded search cfg
          /arch/boot/<arch>/vmlinuz-linux    — kernel (for systemd-boot in the ESP)
          /arch/boot/<arch>/initramfs-*.img  — initramfs
          /loader/loader.conf               — systemd-boot config
          /loader/entries/arch-live.conf    — boot entry
        """
        logger.info("[GRUB2] Generating UEFI boot image (efiboot.img)...")

        efi_img_path = workdir / "EFI" / "efiboot.img"
        efi_img_path.parent.mkdir(parents=True, exist_ok=True)
        efi_binary = workdir / "EFI" / "BOOT" / "BOOTx64.EFI"
        efi_binary.parent.mkdir(parents=True, exist_ok=True)

        iso_label = self._cfg_get("system.iso_label", "ARCH-MODERN")
        arch = self._cfg_get("platform_specific.architecture", "x86_64")
        kernel_name = self._cfg_get("platform_specific.base_kernel", "vmlinuz-linux")
        initramfs_name = self._cfg_get("platform_specific.initramfs", "initramfs-linux.img")

        has_real_chroot = bool(
            chroot_path
            and Path(chroot_path).exists()
            and (Path(chroot_path) / "usr" / "bin" / "grub-mkstandalone").exists()
        )

        if not has_real_chroot:
            # Mock mode: no isolated system available — write a zeroed placeholder FAT image
            # (32 MiB of zeros is enough for xorriso to embed it, even though it won't boot)
            logger.info("[GRUB2] [MOCK] No real chroot — writing placeholder efiboot.img")
            efi_binary.write_bytes(b"\x00" * 512)
            efi_img_path.write_bytes(b"\x00" * (32 * 1024 * 1024))
            logger.warning("[GRUB2] [MOCK] efiboot.img is a placeholder — build a real ISO with a live chroot")
            return True

        chroot = Path(chroot_path)

        # ── Stage area inside chroot /tmp ──────────────────────────────────────
        stage = chroot / "tmp" / "efiboot_stage"
        shutil.rmtree(stage, ignore_errors=True)

        # Subdirectories that mirror what will go into the FAT image
        (stage / "EFI" / "BOOT").mkdir(parents=True, exist_ok=True)
        (stage / f"arch" / "boot" / arch).mkdir(parents=True, exist_ok=True)
        (stage / "loader" / "entries").mkdir(parents=True, exist_ok=True)

        # ── Step 1: Generate grub-embed.cfg and create BOOTx64.EFI ─────────────
        embed_cfg_chroot = stage / "grub-embed.cfg"
        self.generate_embed_cfg(workdir, embed_cfg_chroot)

        grub_modules = (
            "all_video at_keyboard boot btrfs cat chain configfile echo "
            "efifwsetup efinet exfat ext2 fat font gfxmenu gfxterm gzio "
            "halt hfsplus iso9660 jpeg keylayouts linux loadenv loopback "
            "lsefi lsefimmap minicmd normal ntfs part_apple part_gpt "
            "part_msdos png read reboot regexp search search_fs_file "
            "search_fs_uuid search_label serial sleep udf usb video xfs zstd"
        )

        # Paths are relative to chroot root  (/tmp/efiboot_stage/...)
        stage_rel = "/tmp/efiboot_stage"
        chroot_cmd = ["chroot"]
        if os.geteuid() != 0:
            chroot_cmd = ["sudo", "chroot"]

        try:
            cmd_grub = [
                *chroot_cmd, str(chroot), "bash", "-c",
                f"grub-mkstandalone -O x86_64-efi "
                f"--modules=\"{grub_modules}\" "
                f"--locales=\"en@quot\" "
                f"--themes=\"\" "
                f"-o {stage_rel}/EFI/BOOT/BOOTx64.EFI "
                f"boot/grub/grub.cfg={stage_rel}/grub-embed.cfg"
            ]
            result = subprocess.run(cmd_grub, capture_output=True, timeout=180)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd_grub,
                                                    result.stdout, result.stderr)
            logger.info("[GRUB2] BOOTx64.EFI created via grub-mkstandalone in chroot")
        except Exception as e:
            # Captures errors of execution (ex: command inexistente, permissão negada em tempo real)
            error_output = f"Failed to execute the command '{cmd_grub[0]}'. Error:\n{e}"
            logger.error(error_output)
            raise Grub2BootloaderError(error_output)

        # Copy BOOTx64.EFI out to workdir/EFI/BOOT/ as well
        efi_in_stage = stage / "EFI" / "BOOT" / "BOOTx64.EFI"
        if efi_in_stage.exists():
            shutil.copy2(efi_in_stage, efi_binary)

        # ── Step 2: Copy kernel, initramfs and loader files into staging area ──
        for fname, dst_dir in [
            (kernel_name,    stage / "arch" / "boot" / arch),
            (initramfs_name, stage / "arch" / "boot" / arch),
        ]:
            src = workdir / "arch" / "boot" / arch / fname
            if src.exists():
                shutil.copy2(src, dst_dir / fname)
            else:
                logger.warning(f"[GRUB2] efiboot staging: {fname} not found at {src}")

        # Loader config
        loader_src = workdir / "loader"
        if loader_src.exists():
            if (loader_src / "loader.conf").exists():
                shutil.copy2(loader_src / "loader.conf", stage / "loader" / "loader.conf")
            entries_src = loader_src / "entries"
            if entries_src.exists():
                for entry in entries_src.glob("*"):
                    if entry.is_file():
                        shutil.copy2(entry, stage / "loader" / "entries" / entry.name)

        # ── Step 3: Calculate FAT image size and build it inside the chroot ────
        total_bytes = sum(
            f.stat().st_size for f in stage.rglob("*") if f.is_file()
        )
        size_mib = max(64, (total_bytes // (1024 * 1024)) + 16)

        efi_img_chroot = "/tmp/efiboot.img"  # path inside the chroot
        efi_img_host = chroot / "tmp" / "efiboot.img"

        # Create the zero-filled file on the host first to avoid needing /dev/zero inside the chroot
        with open(efi_img_host, "wb") as f:
            f.write(b"\x00" * (size_mib * 1024 * 1024))

        fat_cmds = [
            f"mkfs.fat -n ARCHISO_EFI {efi_img_chroot}",
            # EFI binary
            f"mmd -i {efi_img_chroot} ::/EFI ::/EFI/BOOT",
            f"mcopy -i {efi_img_chroot} {stage_rel}/EFI/BOOT/BOOTx64.EFI ::/EFI/BOOT/BOOTx64.EFI",
            # Kernel + initramfs
            f"mmd -i {efi_img_chroot} ::/arch ::/arch/boot ::/arch/boot/{arch}",
            f"mcopy -i {efi_img_chroot} {stage_rel}/arch/boot/{arch}/{kernel_name} ::/arch/boot/{arch}/{kernel_name}",
            f"mcopy -i {efi_img_chroot} {stage_rel}/arch/boot/{arch}/{initramfs_name} ::/arch/boot/{arch}/{initramfs_name}",
            # loader
            f"mmd -i {efi_img_chroot} ::/loader ::/loader/entries",
        ]

        loader_conf_stage = stage / "loader" / "loader.conf"
        if loader_conf_stage.exists():
            fat_cmds.append(
                f"mcopy -i {efi_img_chroot} {stage_rel}/loader/loader.conf ::/loader/loader.conf"
            )
        entries_stage = stage / "loader" / "entries"
        if entries_stage.exists():
            for entry in entries_stage.glob("*"):
                if entry.is_file():
                    fat_cmds.append(
                        f"mcopy -i {efi_img_chroot} "
                        f"{stage_rel}/loader/entries/{entry.name} "
                        f"::/loader/entries/{entry.name}"
                    )

        try:
            chroot_cmd = ["chroot"]
            if os.geteuid() != 0:
                chroot_cmd = ["sudo", "chroot"]
            cmd_fat = [*chroot_cmd, str(chroot), "bash", "-c", " && ".join(fat_cmds)]
            result = subprocess.run(cmd_fat, capture_output=True, timeout=300)
            if result.returncode != 0:
                stderr_text = result.stderr.decode(errors="replace")
                raise subprocess.CalledProcessError(
                    result.returncode, cmd_fat, result.stdout, result.stderr
                )
            shutil.copy2(efi_img_host, efi_img_path)
            logger.info(f"[GRUB2] efiboot.img created ({size_mib} MiB) via chroot mtools: {efi_img_path}")
            return True

        except subprocess.CalledProcessError as e:
            # Captures erros de execução (ex: comando inexistente, permissão negada em tempo real)
            error_output = f"Falha ao executar o comando '{cmd_fat[0]}'. Status de Erro:\n{e.stderr}"
            logger.error(error_output)
            raise Grub2BootloaderError(error_output)
        except Exception as e:
            raise Grub2BootloaderError(f"Unexpected error during efiboot.img creation: {type(e).__name__}: {str(e)}")
        finally:
            # Clean up staging area and tmp img inside chroot
            shutil.rmtree(stage, ignore_errors=True)
            efi_img_host.unlink(missing_ok=True)

    def validate(self, workdir: Path) -> bool:
        """Validate that the required bootloader files exist."""
        return (workdir / "boot" / "grub" / "grub.cfg").exists()