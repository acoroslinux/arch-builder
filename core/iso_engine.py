# -*- coding: utf-8 -*-
"""
core/iso_engine.py

Central build engine definitions.
``ISOBuilder`` is the canonical high-level build API.
``ArchBuilder`` remains as a backward-compatible alias.
"""

from abc import ABC, abstractmethod
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from core.config_loader import Config
from core.bootloaders.grub2 import Grub2Bootloader
from core.bootloaders.syslinux import SyslinuxBootloader
from core.chroot_manager import ChrootManager
from core.customizer import SystemConfigurator
from core.path_utils import resolve_from_project

try:
    from .logger_setup import setup_logger
except ImportError:  # pragma: no cover
    def setup_logger(*_, **__):  # type: ignore
        import logging

        logging.basicConfig(level=logging.INFO)
        return logging.getLogger()

logger = setup_logger(__name__)
_ENGINE_REGISTRY: Dict[str, Type["BaseEngine"]] = {}

__all__ = [
    "ArchBuilder",
    "ArchEngine",
    "BaseEngine",
    "Config",
    "ISOBuilder",
    "ISOBuilderError",
    "ISOEngine",
    "LegacyEngine",
]

class ISOBuilderError(Exception):
    """Raised when the build orchestration flow cannot proceed."""

class ISOEngine(ABC):
    """Abstract base for architecture-specific build engines."""

    @classmethod
    def register(cls, arch_name: str):
        def decorator(engine_class: Type["BaseEngine"]):
            if arch_name in _ENGINE_REGISTRY:
                raise TypeError(f"Architecture '{arch_name}' is already registered.")
            _ENGINE_REGISTRY[arch_name] = engine_class
            return engine_class

        return decorator

class BaseEngine(ISOEngine):
    """Common engine behavior shared across all architecture-specific engines."""

    def __init__(self, arch: str, config: Config, toolchain: Any):
        self.arch = arch
        self.config = config
        self.toolchain = toolchain
        self.logger = getattr(toolchain, "logger", setup_logger(self.__class__.__name__))

    def _system_config(self) -> Dict[str, Any]:
        # Alterar para usar o novo bloco system_info em vez de system
        return self.config.get("system_info", {})
    def _cfg_get(self, key: str, default: Any = None) -> Any:
        """Compatibility wrapper for config.get(key[, default])."""
        try:
            value = self.config.get(key, default)
        except TypeError:
            value = self.config.get(key)
        return default if value is None else value

    def _workdir_base(self) -> str:
        system = self._system_config()
        configured = (
            self.config.get("system.workdir_base")
            or system.get("workdir_base")
            or system.get("workdir")
            or "arch-builder/workdir"
        )
        return str(resolve_from_project(str(configured)))

    def _boot_mountpoint(self) -> str:
        chroot_manager = getattr(self.toolchain, "chroot_manager", None)
        if chroot_manager and getattr(chroot_manager, "chroot_path", None):
            mountpoint = Path(chroot_manager.chroot_path) / "boot"
        else:
            mountpoint = Path(self._workdir_base()) / "mnt" / "boot"

        try:
            mountpoint.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            fallback = resolve_from_project(
                Path("arch-builder") / "fallback" / self.arch / "boot"
            )
            temp_fallback = Path(tempfile.gettempdir()) / "arch-builder-fallback" / self.arch / "boot"
            selected = None
            for candidate in (fallback, temp_fallback):
                try:
                    candidate.mkdir(parents=True, exist_ok=True)
                    selected = candidate
                    break
                except PermissionError:
                    continue
            if selected is None:
                raise
            self.logger.warning(
                f"Boot mountpoint '{mountpoint}' is not writable. Falling back to '{selected}'."
            )
            mountpoint = selected
        return str(mountpoint)

    def _normalize_packages(self, packages: Any) -> List[str]:
        if not packages:
            return []
        normalized: List[str] = []
        for item in packages:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    normalized.append(str(name))
            else:
                normalized.append(str(item))
        return normalized

    def _run_command(self, command: List[str], chroot_path: Optional[str] = None) -> Any:
        if hasattr(self.toolchain, "run_command"):
            return self.toolchain.run_command(command, chroot_path=chroot_path)
        if hasattr(self.toolchain, "execute_command"):
            return self.toolchain.execute_command(command, chroot_path=chroot_path)
        raise ISOBuilderError("Toolchain does not expose run_command or execute_command.")

    def _package_plan(self) -> Dict[str, List[str]]:
        """Build a normalized package installation plan from legacy and new config keys."""
        legacy_packages = self._normalize_packages(self._cfg_get("packages"))
        platform_packages = self._normalize_packages(self._cfg_get("platform_specific.packages"))
        legacy = list(dict.fromkeys(legacy_packages + platform_packages))
        official = self._normalize_packages(self._cfg_get("package_sources.official", []))
        aur = self._normalize_packages(self._cfg_get("package_sources.aur", []))
        local_paths = self._normalize_packages(
            self._cfg_get("package_sources.local_packages", [])
        )

        # Load all matching package files from a user-provided local package directory.
        local_dir = self._cfg_get("package_sources.local_dir")
        local_glob = self._cfg_get("package_sources.local_glob", "*.pkg.tar*")
        if local_dir:
            local_dir_path = resolve_from_project(str(local_dir))
            if local_dir_path.exists() and local_dir_path.is_dir():
                for candidate in sorted(local_dir_path.glob(str(local_glob))):
                    local_paths.append(str(candidate))
            else:
                self.logger.warning(
                    f"Configured local package directory not found: {local_dir_path}"
                )

        # Keep order while deduplicating.
        official_all = list(dict.fromkeys([*legacy, *official]))
        aur = list(dict.fromkeys(aur))
        local_paths = list(dict.fromkeys(local_paths))

        return {
            "official": official_all,
            "aur": aur,
            "local_paths": local_paths,
        }

    def setup_workdir(self, workdir: Optional[Union[str, Path]] = None) -> Path:
        target = Path(workdir) if workdir else Path(self._workdir_base())
        if not target.is_absolute():
            target = resolve_from_project(target)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            fallback = resolve_from_project(Path("arch-builder") / "fallback" / self.arch)
            temp_fallback = Path(tempfile.gettempdir()) / "arch-builder-fallback" / self.arch
            selected = None
            for candidate in (fallback, temp_fallback):
                try:
                    candidate.mkdir(parents=True, exist_ok=True)
                    selected = candidate
                    break
                except PermissionError:
                    continue
            if selected is None:
                raise
            self.logger.warning(
                f"Workdir '{target}' is not writable in the current mode. Falling back to '{selected}'."
            )
            target = selected
        return target

    @abstractmethod
    def setup_chroot(self, workdir: str) -> None:
        """Prepare the chroot environment."""

    @abstractmethod
    def install_packages(self) -> None:
        """Install target packages inside the chroot."""

    @abstractmethod
    def build_bootloaders(self, mountpoint: str) -> None:
        """Generate bootloader artifacts for the target architecture."""

    @abstractmethod
    def post_install_configure(self) -> None:
        """Run post-install configuration steps."""

    @abstractmethod
    def finalize_isofile(self, output_path: str) -> None:
        """Produce the final ISO file."""

@ISOEngine.register("x86_64")
class ArchEngine(BaseEngine):
    """Engine in charge of x86_64 builds."""

    def _prepare_grub_boot_tree(self, chroot_root: Path, iso_uuid: str = "") -> None:
        """Generate GRUB configuration inside the active rootfs before ISO creation."""
        from core.bootloaders.grub2 import Grub2Bootloader

        # Use the root device ID from config or a sensible default
        root_device_id = self.config.get("system.root_device_id", "ARCHISO_UUID_PLACEHOLDER")
        bootloader = Grub2Bootloader(self.config, root_device_id, iso_uuid=iso_uuid)
        bootloader.prepare_files(chroot_root)

    def setup_chroot(self, workdir: str) -> None:
        self.logger.info(f"[setup_chroot] Preparing chroot at {workdir}")

        # 3. Prepare a build toolchain (host tools or isolated Arch bootstrap in real mode).
        # These values are read from the toolchain object, which is set up by the orchestrator.
        force_isolated = getattr(self.toolchain, "force_isolated", False) or bool(
            self.config.get("system_info.force_isolated_toolchain", False)
        )
        pacman_retries = int(
            getattr(self.toolchain, "pacman_retries", 3)
        )
        diagnostics_enabled = getattr(self.toolchain, "diagnostics_enabled", False) or bool(
            self.config.get("system_info.toolchain_debug", False)
        )

        # In isolated mode, ensure /airootfs exists inside the build chroot for package installation
        build_chroot = getattr(self.toolchain, "build_chroot", None)
        if not force_isolated and build_chroot:
            iso_rootfs = Path(build_chroot) / "airootfs"
            if iso_rootfs.exists():
                shutil.rmtree(iso_rootfs, ignore_errors=True)
            (Path(build_chroot) / "airootfs").mkdir(parents=True, exist_ok=True)
            
        # Ensure boot mountpoint exists
        self._boot_mountpoint()

    def _prepare_grub_iso_root(self, effective_root: Path) -> Path:
        """Create a dedicated ISO source tree containing the boot directory expected by GRUB."""
        self._prepare_grub_boot_tree(effective_root)

        source_boot = effective_root / "boot"
        staging_root = effective_root / "tmp" / "arch-builder-iso-root"
        staging_boot = staging_root / "boot"

        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)

        staging_root.mkdir(parents=True, exist_ok=True)
        if source_boot.exists():
            shutil.copytree(source_boot, staging_boot, dirs_exist_ok=True)
        else:
            staging_boot.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            f"[build_bootloaders] GRUB staging tree prepared: rootfs={effective_root} staging={staging_root}"
        )

        return staging_root

    def install_packages(self) -> None:
        plan = self._package_plan()
        self.logger.info("Starting package installation with cache management.")
        chroot_manager = getattr(self.toolchain, "chroot_manager", None)
        if chroot_manager and hasattr(chroot_manager, "install_packages"):
            chroot_manager.install_packages(plan)
        elif plan["official"]:
            self._run_command(["pacman", "-S", "--noconfirm", *plan["official"]], chroot_path=self._workdir_base())

        if not chroot_manager and (plan["aur"] or plan["local_paths"]):
            self.logger.warning(
                "AUR/local package installation requires chroot manager integration; only official packages were processed."
            )
        self.logger.info("Packages installed successfully.")

    def _create_squashfs(self, source_dir: Path, output_path: Path) -> None:
        """Create a squashfs filesystem from a directory using mksquashfs.

        Runs mksquashfs directly on the host (not inside chroot) because
        the source directory path is a host-absolute path.
        """
        self.logger.info(f"[squashfs] Creating squashfs from {source_dir} -> {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        is_mock = getattr(self.toolchain, "mode", "mock") == "mock"
        if is_mock:
            self.logger.info(f"[squashfs] [MOCK] Would create squashfs: {output_path} from {source_dir}")
            output_path.write_text("mock-squashfs-content")
            return

        # Exclude virtual filesystems and unnecessary directories
        exclude_dirs = [
            "proc/*", "sys/*", "dev/*", "run/*", "tmp/*",
            "mnt/*", "lost+found", ".cache",
        ]
        command = [
            "mksquashfs",
            str(source_dir),
            str(output_path),
            "-comp", "zstd",
            "-b", "1M",
            "-noappend",
        ]
        for ex in exclude_dirs:
            command.extend(["-e", ex])

        self.logger.info(f"[squashfs] Running: {' '.join(command)}")
        try:
            self._run_command(command)
        except Exception as e:
            self.logger.error(f"mksquashfs failed: {e}")
            raise
        self.logger.info(f"[squashfs] Created: {output_path}")

    def _generate_grub_boot_images(self, staging_dir: Path, effective_root: Path, iso_uuid: str = "") -> None:
        """Generate GRUB BIOS boot image (boot.img) and EFI binary (BOOTx64.EFI) using the chroot."""
        grub_dir = staging_dir / "boot" / "grub"
        grub_dir.mkdir(parents=True, exist_ok=True)
        efi_dir = staging_dir / "EFI" / "BOOT"
        efi_dir.mkdir(parents=True, exist_ok=True)

        is_mock = getattr(self.toolchain, "mode", "mock") == "mock"
        if is_mock:
            self.logger.info("[grub] [MOCK] Would generate GRUB BIOS and EFI boot images")
            (grub_dir / "boot.img").write_bytes(b"\x00" * 512)
            (efi_dir / "BOOTx64.EFI").write_bytes(b"")
            return

        # Paths inside the chroot where the grub packages install modules
        chroot_efi_modules = effective_root / "usr" / "lib" / "grub" / f"{self.arch}-efi"
        chroot_bios_modules = effective_root / "usr" / "lib" / "grub" / "i386-pc"

        # 1. --- Generate GRUB BIOS boot image (boot.img) ---
        boot_img_dest = grub_dir / "boot.img"
        if chroot_bios_modules.exists():
            self.logger.info("[grub] Generating GRUB BIOS boot image in chroot...")
            try:
                cmd = [
                    "chroot", str(effective_root), "bash", "-c",
                    "grub-mkimage -d /usr/lib/grub/i386-pc -o /tmp/boot.img -O i386-pc -p /boot/grub "
                    "biosdisk iso9660 part_msdos part_gpt ext2 fat ntfs search_fs_uuid search_label"
                ]
                self._run_command(cmd)
                shutil.copy2(effective_root / "tmp" / "boot.img", boot_img_dest)
                (effective_root / "tmp" / "boot.img").unlink(missing_ok=True)
                self.logger.info(f"[grub] Created BIOS boot image: {boot_img_dest}")
            except Exception as e:
                self.logger.warning(f"[grub] Failed to create BIOS boot image: {e}")
                boot_img_dest.write_bytes(b"\x00" * 512)
        else:
            self.logger.warning(f"[grub] GRUB BIOS modules not found at {chroot_bios_modules}")
            boot_img_dest.write_bytes(b"\x00" * 512)

        # 2. --- Generate GRUB EFI binary (BOOTx64.EFI) ---
        efi_binary_dest = efi_dir / "BOOTx64.EFI"
        if chroot_efi_modules.exists():
            self.logger.info("[grub] Generating GRUB EFI binary in chroot...")
            try:
                # Build the grub-embed.cfg using the same logic as mkarchiso:
                # search by the UUID file /boot/<iso_uuid>.uuid, then configfile grub.cfg
                iso_label = self.config.get("system.iso_label") or self.config.get("build_environment.iso_label") or "ARCH-MODERN"
                search_filename = f"/boot/{iso_uuid}.uuid" if iso_uuid else ""
                if search_filename:
                    embed_cfg = (
                        f"search --no-floppy --set=root --file {search_filename}\n"
                        f"set prefix=($root)/boot/grub\n"
                        f"configfile ($root)/boot/grub/grub.cfg\n"
                    )
                else:
                    embed_cfg = (
                        f"search --no-floppy --set=root --label {iso_label}\n"
                        f"set prefix=($root)/boot/grub\n"
                        f"configfile ($root)/boot/grub/grub.cfg\n"
                    )
                (effective_root / "tmp" / "grub-embed.cfg").write_text(embed_cfg)

                # Compile the standalone EFI image inside the chroot
                cmd = [
                    "chroot", str(effective_root), "bash", "-c",
                    f"grub-mkimage -d /usr/lib/grub/{self.arch}-efi -o /tmp/BOOTx64.EFI -O {self.arch}-efi "
                    "-c /tmp/grub-embed.cfg -p /boot/grub "
                    "efifwsetup efinet efi_uga fat iso9660 part_gpt part_msdos search_fs_uuid search_label "
                    "normal boot configfile linux loopback chain"
                ]
                self._run_command(cmd)
                shutil.copy2(effective_root / "tmp" / "BOOTx64.EFI", efi_binary_dest)
                
                # Cleanup
                (effective_root / "tmp" / "BOOTx64.EFI").unlink(missing_ok=True)
                (effective_root / "tmp" / "grub-embed.cfg").unlink(missing_ok=True)
                self.logger.info(f"[grub] Created EFI binary: {efi_binary_dest}")
            except Exception as e:
                self.logger.warning(f"[grub] Failed to create EFI binary in chroot: {e}")
                # Clean up any leftover temp files
                (effective_root / "tmp" / "BOOTx64.EFI").unlink(missing_ok=True)
                (effective_root / "tmp" / "grub-embed.cfg").unlink(missing_ok=True)
                efi_binary_dest.write_bytes(b"")
        else:
            self.logger.warning(f"[grub] GRUB EFI modules not found at {chroot_efi_modules}")
            efi_binary_dest.write_bytes(b"")

    def build_bootloaders(self, mountpoint: str) -> None:
        """Build the complete Arch Linux live ISO directory structure.

        Standard Arch ISO layout::

            /
            ├── boot/
            │   ├── vmlinuz-linux       # Kernel
            │   ├── initramfs-linux.img # Initramfs
            │   └── grub/
            │       ├── grub.cfg        # GRUB config
            │       └── boot.img        # GRUB BIOS boot image
            ├── EFI/
            │   └── BOOT/
            │       └── BOOTx64.EFI     # GRUB EFI binary
            ├── loader/
            │   ├── loader.conf         # systemd-boot config
            │   └── entries/
            │       └── arch-live.conf  # Boot entry
            └── arch/
                └── x86_64/
                    └── airootfs.sfs    # Squashfs root filesystem
        """
        effective_root = Path(mountpoint).parent

        # --- Generate ISO UUID (matches mkarchiso: TZ=UTC date +%F-%H-%M-%S-00) ---
        # mkarchiso creates /boot/<iso_uuid>.uuid on the ISO so the archiso hook
        # can find the ISO device by scanning all block devices for that file.
        import datetime
        iso_uuid = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S-00")

        # Generate GRUB configuration (grub.cfg) inside the airootfs
        self._prepare_grub_boot_tree(effective_root, iso_uuid=iso_uuid)

        # Create the ISO staging directory
        iso_staging = effective_root.parent / "iso-staging"
        if iso_staging.exists():
            shutil.rmtree(iso_staging, ignore_errors=True)

        # Create directory structure
        iso_boot = iso_staging / "boot"
        iso_boot.mkdir(parents=True, exist_ok=True)
        (iso_staging / "EFI" / "BOOT").mkdir(parents=True, exist_ok=True)
        (iso_staging / "loader" / "entries").mkdir(parents=True, exist_ok=True)

        search_filename = f"/boot/{iso_uuid}.uuid"
        # Create the empty UUID marker file (critical for archiso hook to find the device)
        (iso_boot / f"{iso_uuid}.uuid").touch()
        self.logger.info(f"[boot] Created ISO UUID marker: boot/{iso_uuid}.uuid")

        # --- Copy kernel and initramfs from airootfs into the archiso standard path ---
        # mkarchiso places kernel at: /${install_dir}/boot/${arch}/vmlinuz-linux
        # i.e.: arch/boot/x86_64/vmlinuz-linux
        source_boot = effective_root / "boot"
        kernel_name = self.config.get("platform_specific.base_kernel", "vmlinuz-linux")
        initramfs_name = self.config.get("platform_specific.initramfs", "initramfs-linux.img")
        install_dir = "arch"
        
        # Create target directory: arch/boot/x86_64/
        iso_kernel_dir = iso_staging / install_dir / "boot" / self.arch
        iso_kernel_dir.mkdir(parents=True, exist_ok=True)

        if source_boot.exists():
            kernel_src = source_boot / kernel_name
            if kernel_src.exists():
                shutil.copy2(kernel_src, iso_kernel_dir / kernel_name)
                self.logger.info(f"[boot] Copied kernel to {install_dir}/boot/{self.arch}/{kernel_name}")
            else:
                self.logger.warning(f"[boot] Kernel not found at {kernel_src}")

            # Copy microcode images to /arch/boot/ (not arch-specific subfolder, matching mkarchiso)
            for ucode in ["intel-ucode.img", "amd-ucode.img"]:
                ucode_src = source_boot / ucode
                if ucode_src.exists():
                    shutil.copy2(ucode_src, iso_kernel_dir / ucode)
                    self.logger.info(f"[boot] Copied microcode: {ucode}")

            initramfs_src = source_boot / initramfs_name
            if initramfs_src.exists():
                shutil.copy2(initramfs_src, iso_kernel_dir / initramfs_name)
                self.logger.info(f"[boot] Copied initramfs to {install_dir}/boot/{self.arch}/{initramfs_name}")
            else:
                self.logger.warning(f"[boot] Initramfs not found at {initramfs_src}")

            grub_cfg_src = source_boot / "grub" / "grub.cfg"
            if grub_cfg_src.exists():
                (iso_boot / "grub").mkdir(parents=True, exist_ok=True)
                shutil.copy2(grub_cfg_src, iso_boot / "grub" / "grub.cfg")
                self.logger.info("[boot] Copied grub.cfg")

            # Copy themes and fonts directories for GRUB theme support
            grub_themes_src = source_boot / "grub" / "themes"
            if grub_themes_src.exists():
                shutil.copytree(grub_themes_src, iso_boot / "grub" / "themes", dirs_exist_ok=True)
                self.logger.info("[boot] Copied GRUB themes")

            # Ensure the unicode font is present on the ISO for graphical terminal menu rendering
            iso_fonts_dir = iso_boot / "grub" / "fonts"
            iso_fonts_dir.mkdir(parents=True, exist_ok=True)
            copied_font = False

            # 1. Try copying from chroot /boot/grub/fonts
            if (source_boot / "grub" / "fonts" / "unicode.pf2").exists():
                shutil.copy2(source_boot / "grub" / "fonts" / "unicode.pf2", iso_fonts_dir / "unicode.pf2")
                copied_font = True
            # 2. Try copying from chroot /usr/share/grub/unicode.pf2
            elif (effective_root / "usr" / "share" / "grub" / "unicode.pf2").exists():
                shutil.copy2(effective_root / "usr" / "share" / "grub" / "unicode.pf2", iso_fonts_dir / "unicode.pf2")
                copied_font = True
            # 3. Try copying from host /usr/share/grub/unicode.pf2
            elif Path("/usr/share/grub/unicode.pf2").exists():
                shutil.copy2("/usr/share/grub/unicode.pf2", iso_fonts_dir / "unicode.pf2")
                copied_font = True

            if copied_font:
                self.logger.info("[boot] Copied GRUB unicode font to ISO boot tree")
            else:
                self.logger.warning("[boot] GRUB unicode font could not be located on chroot or host")
        else:
            self.logger.warning(f"[boot] Source boot directory not found at {source_boot}")

        # --- Generate Syslinux boot files for legacy BIOS ---
        syslinux_loader = SyslinuxBootloader(self.config)
        syslinux_loader.prepare_files(iso_staging, iso_uuid=iso_uuid)
        syslinux_loader.generate_boot_image(iso_staging, effective_root)

        # --- Generate GRUB boot images (BIOS + UEFI) ---
        self._generate_grub_boot_images(iso_staging, effective_root, iso_uuid=iso_uuid)

        # --- Generate UEFI FAT boot image (efiboot.img) ---
        grub_loader = Grub2Bootloader(self.config, root_device_id="", iso_uuid=iso_uuid)
        grub_loader.generate_boot_image(iso_staging, effective_root)

        # --- Create squashfs of the airootfs ---
        arch_dir = iso_staging / "arch" / self.arch
        arch_dir.mkdir(parents=True, exist_ok=True)
        squashfs_path = arch_dir / "airootfs.sfs"
        self._create_squashfs(effective_root, squashfs_path)

        # --- Create systemd-boot loader config from template ---
        iso_label = self.config.get("system.iso_label") or self.config.get("build_environment.iso_label") or "ARCH-MODERN"
        kernel_params = self.config.get("boot.kernel_params", "loglevel=4 quiet")
        cmdline = f"{kernel_params} rw systemd.setenv=SYSTEMD_SULOGIN_FORCE=1"

        _loader_conf_tmpl = resolve_from_project("configs/templates/efiboot/loader/loader.conf")
        if _loader_conf_tmpl.exists():
            shutil.copy2(_loader_conf_tmpl, iso_staging / "loader" / "loader.conf")
        else:
            (iso_staging / "loader" / "loader.conf").write_text("timeout 15\ndefault arch-live.conf\n")

        # --- Create systemd-boot entry from template ---
        # Use archisosearchuuid (matching mkarchiso) so the hook finds the ISO by the
        # UUID marker file /boot/<iso_uuid>.uuid rather than by volume label alone.
        _entry_tmpl = resolve_from_project("configs/templates/efiboot/loader/entries/arch-live.conf")
        if _entry_tmpl.exists():
            _entry_content = _entry_tmpl.read_text()
            _replacements = {
                "@@BOOT_TITLE@@": "Arch Modern",
                "@@ARCH@@": self.arch,
                "@@KERNEL_FILE@@": kernel_name,
                "@@INITRAMFS_FILE@@": initramfs_name,
                "@@ISO_LABEL@@": iso_label,
                "@@ARCHISO_UUID@@": iso_uuid,
                "@@BOOT_CMDLINE@@": cmdline,
                "@@INSTALL_DIR@@": install_dir,
            }
            for _k, _v in _replacements.items():
                _entry_content = _entry_content.replace(_k, _v)
            (iso_staging / "loader" / "entries" / "arch-live.conf").write_text(_entry_content)
        else:
            entry_content = (
                f"title    Arch Modern ({self.arch}, UEFI)\n"
                f"sort-key 01\n"
                f"linux    /{install_dir}/boot/{self.arch}/{kernel_name}\n"
                f"initrd   /{install_dir}/boot/{self.arch}/{initramfs_name}\n"
                f"options  archisobasedir={install_dir} archisosearchuuid={iso_uuid} {cmdline}\n"
            )
            (iso_staging / "loader" / "entries" / "arch-live.conf").write_text(entry_content)

        # Store the ISO staging path for finalize_isofile
        self._iso_staging = iso_staging
        self.logger.info(f"[build] ISO staging directory: {iso_staging}")

    def finalize_isofile(self, output_path: str) -> None:
        """Create the final bootable ISO using grub-mkrescue.

        grub-mkrescue is the standard tool for creating bootable Arch Linux ISOs.
        It handles all the complexity of:
        - Creating proper El Torito boot images for BIOS
        - Creating EFI boot images for UEFI
        - Making the ISO hybrid (bootable from both BIOS and UEFI)
        - Embedding all required GRUB modules

        In mock mode, this method only logs the intent without executing.
        """
        iso_source = getattr(self, "_iso_staging", None)
        if not iso_source or not iso_source.exists():
            raise ISOBuilderError(
                "ISO staging directory not found. build_bootloaders() must be called first."
            )

        output_abs = str(resolve_from_project(output_path))
        Path(output_abs).parent.mkdir(parents=True, exist_ok=True)

        # Check if we're in mock mode - skip actual execution
        is_mock = getattr(self.toolchain, "mode", "mock") == "mock"
        
        iso_label = self.config.get("system.iso_label") or self.config.get("build_environment.iso_label") or "ARCH-MODERN"
        command = [
            "xorriso",
            "-as", "mkisofs",
            "-iso-level", "3",
            "-full-iso9660-filenames",
            "-joliet",
            "-joliet-long",
            "-rational-rock",
            "-volid", iso_label,
            "-appid", "Arch Modern Live",
            "-publisher", "acoroslinux",
            "-preparer", "arch-builder",
            # BIOS syslinux parameters (archiso official layout: boot/syslinux/)
            "-eltorito-boot", "boot/syslinux/isolinux.bin",
            "-eltorito-catalog", "boot/syslinux/boot.cat",
            "-no-emul-boot",
            "-boot-load-size", "4",
            "-boot-info-table",
            "-isohybrid-mbr", str(iso_source / "boot" / "syslinux" / "isohdpfx.bin"),
            "--mbr-force-bootable",
            "-partition_offset", "16",
            # UEFI parameters
            "-append_partition", "2", "C12A7328-F81F-11D2-BA4B-00A0C93EC93B", str(iso_source / "EFI" / "efiboot.img"),
            "-isohybrid-gpt-basdat",
            "-eltorito-alt-boot",
            "-e", "--interval:appended_partition_2:all::",
            "-no-emul-boot",
            "-output", output_abs,
            str(iso_source)
        ]

        if is_mock:
            self.logger.info(f"[finalize] [MOCK] Would create ISO: {output_abs} from {iso_source}")
            self.logger.info(f"[finalize] [MOCK] Command: {' '.join(command)}")
            return

        self.logger.info(f"[finalize] Creating bootable hybrid ISO with xorriso: {output_abs}")
        self.logger.info(f"[finalize] Command: {' '.join(command)}")

        try:
            self._run_command(command)
        except Exception as e:
            # If the ISO file was successfully generated despite a post-generation crash (e.g. SIGSEGV on clean-up)
            if Path(output_abs).exists() and Path(output_abs).stat().st_size > 1000000:
                self.logger.warning(
                    f"xorriso reported an exit error/crash ({e}), "
                    f"but the ISO file was successfully generated at {output_abs} "
                    f"({Path(output_abs).stat().st_size} bytes)."
                )
            else:
                self.logger.error(f"xorriso failed: {e}")
                raise ISOBuilderError(f"xorriso failed: {e}")

        self.logger.info(f"[finalize] Bootable ISO created: {output_abs}")

    def _generate_initramfs(self) -> None:
        """Generate the initramfs inside the airootfs using mkinitcpio.

        This must be done after all packages are installed and before
        creating the squashfs, so that /boot/vmlinuz-linux and
        /boot/initramfs-linux.img exist for the ISO.

        Requires mounting /proc, /dev, /sys inside the airootfs chroot
        for mkinitcpio to function properly.
        """
        self.logger.info("[initramfs] Generating initramfs with mkinitcpio...")
        chroot_manager = getattr(self.toolchain, "chroot_manager", None)
        if not chroot_manager:
            self.logger.warning("[initramfs] No chroot manager available, skipping")
            return

        # Get the run path (build chroot for isolated mode)
        run_path = None
        if self.toolchain and getattr(self.toolchain, "build_chroot", None):
            run_path = str(self.toolchain.build_chroot)

        if not run_path:
            self.logger.warning("[initramfs] No build chroot path available")
            return

        airootfs_path = Path(run_path) / "airootfs"

        # Mount required filesystems inside airootfs for mkinitcpio
        import subprocess
        import os
        def _sudo_run(cmd, check=True):
            full = cmd if os.geteuid() == 0 else ["sudo", *cmd]
            return subprocess.run(full, check=check, capture_output=True, text=True)

        # Mount proc, sys, dev inside airootfs
        mounts = [
            ("/proc", airootfs_path / "proc", "--bind"),
            ("/sys", airootfs_path / "sys", "--bind"),
            ("/dev", airootfs_path / "dev", "--bind"),
        ]
        for src, dst, opts in mounts:
            dst.mkdir(parents=True, exist_ok=True)
            try:
                with open("/proc/mounts", "r") as f:
                    mounted_paths = [line.split()[1] for line in f.readlines() if len(line.split()) > 1]
                if os.path.abspath(str(dst)) in mounted_paths:
                    self.logger.debug(f"{dst} is already mounted, skipping.")
                    continue
            except Exception:
                pass
            _sudo_run(["mount", opts, str(src), str(dst)], check=False)

        try:
            # Determine which kernel preset to use
            kernel_name = self.config.get("platform_specific.base_kernel", "vmlinuz-linux")
            kernel_preset = kernel_name.replace("vmlinuz-", "")

            # Run mkinitcpio inside the airootfs chroot
            self.logger.info(f"[initramfs] Running mkinitcpio -p {kernel_preset} in airootfs...")
            chroot_manager.run_command(
                ["chroot", "/airootfs", "mkinitcpio", "-p", kernel_preset],
                chroot_path=run_path,
            )
            self.logger.info(f"[initramfs] Generated initramfs for kernel: {kernel_preset}")

            # Verify kernel and initramfs exist
            kernel_file = airootfs_path / "boot" / kernel_name
            initramfs_file = airootfs_path / "boot" / f"initramfs-{kernel_preset}.img"
            if kernel_file.exists():
                self.logger.info(f"[initramfs] Kernel found: {kernel_file} ({kernel_file.stat().st_size} bytes)")
            if initramfs_file.exists():
                self.logger.info(f"[initramfs] Initramfs found: {initramfs_file} ({initramfs_file.stat().st_size} bytes)")

        except Exception as e:
            self.logger.error(f"[initramfs] Failed to generate initramfs: {e}")
        finally:
            # Unmount filesystems
            for src, dst, opts in reversed(mounts):
                _sudo_run(["umount", "-l", str(dst)], check=False)

    def post_install_configure(self) -> None:
        self.logger.info("Starting post-install configuration...")
        chroot_manager = getattr(self.toolchain, "chroot_manager", None)
        if chroot_manager and hasattr(chroot_manager, "generate_fstab"):
            fstab_result = chroot_manager.generate_fstab()
            self.logger.debug(f"Generated fstab: {fstab_result}")

        # Apply full customization graph from config (users, services, files, locale, etc.).
        if chroot_manager:
            configurator = SystemConfigurator(chroot=chroot_manager)
            configurator.load_from_config(self.config)
            configurator.apply()
            self.logger.info(
                "Live ISO customizations applied (users/services/files/autologin settings)."
            )
            # Generate initramfs after applying customizations (so the generated /etc/mkinitcpio.conf is used)
            self._generate_initramfs()
            return

        # Legacy fallback: keep service enabling if no chroot manager is present.
        self.logger.info("Enabling essential services with systemctl...")
        for service in ["NetworkManager", "ssh"]:
            self._run_command(
                ["systemctl", "enable", "--now", f"{service}.service"],
                chroot_path=self._workdir_base(),
            )
            self.logger.info(f"Service '{service}' enabled.")

@ISOEngine.register("i386")
class LegacyEngine(ArchEngine):
    """Legacy engine that currently reuses the x86_64 workflow."""

@ISOEngine.register("aarch64")
class Aarch64Engine(ArchEngine):
    """ARM64 engine reusing the generic build workflow."""

@ISOEngine.register("arm64")
class Arm64Engine(ArchEngine):
    """Alias ARM64 engine reusing the generic build workflow."""

class ISOBuilder:
    """Canonical high-level build orchestrator used by the project."""

    def __init__(
        self,
        arch: str,
        config: Config,
        toolchain: Optional[Any] = None,
        chroot_manager: Optional[ChrootManager] = None,
    ):
        self.arch = arch.lower()
        self.config = config if isinstance(config, Config) else Config(config)
        self.toolchain = self._coerce_toolchain(toolchain, chroot_manager)
        self.engine = self._select_engine()

    def _coerce_toolchain(
        self, toolchain: Optional[Any], chroot_manager: Optional[ChrootManager]
    ) -> Any:
        if toolchain is None:
            toolchain = SimpleNamespace()

        if not hasattr(toolchain, "logger"):
            toolchain.logger = setup_logger("ISOBuilder")

        if not hasattr(toolchain, "run_command") and hasattr(toolchain, "execute_command"):
            toolchain.run_command = toolchain.execute_command

        if not hasattr(toolchain, "run_command"):
            raise ISOBuilderError("Provided toolchain is missing a command runner.")

        if chroot_manager is not None:
            toolchain.chroot_manager = chroot_manager
        elif not hasattr(toolchain, "chroot_manager"):
            toolchain.chroot_manager = ChrootManager(workdir=self._default_chroot_path())

        return toolchain

    def _default_chroot_path(self) -> str:
        system = self.config.get("system") or self.config.get("build_environment") or {}
        base = (
            self.config.get("system.workdir_base")
            or system.get("workdir_base")
            or system.get("workdir")
            or "arch-builder/workdir"
        )
        return str(resolve_from_project(str(base)))

    def _select_engine(self) -> BaseEngine:
        try:
            engine_class = _ENGINE_REGISTRY[self.arch]
        except KeyError as exc:
            raise NotImplementedError(f"Architecture '{self.arch}' is not supported.") from exc
        return engine_class(self.arch, self.config, self.toolchain)

    def build(self, output_path: Union[str, Path], workdir: Optional[Union[str, Path]] = None) -> Path:
        output_path = Path(output_path)
        try:
            workdir_path = self.engine.setup_workdir(workdir)
            self.engine.setup_chroot(str(workdir_path))
            self.engine.install_packages()
            self.engine.post_install_configure()
            self.engine.build_bootloaders(self.engine._boot_mountpoint())
            self.engine.finalize_isofile(str(output_path))
            logger.info("=== Build completed successfully! ===")
            return output_path
        except Exception as exc:
            logger.error(f"Critical failure during build: {exc}")
            raise ISOBuilderError(str(exc)) from exc

    def build_iso(self, output_path: Union[str, Path]) -> Path:
        return self.build(output_path)

class ArchBuilder(ISOBuilder):
    """Backward-compatible alias for the historic builder name."""

    def __init__(self, arch_name: str, config: Config, toolchain: Optional[Any] = None):
        super().__init__(arch_name, config, toolchain=toolchain)

if __name__ == "__main__":
    pass

