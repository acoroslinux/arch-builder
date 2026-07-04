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
        legacy = self._normalize_packages(
            self._cfg_get("packages") or self._cfg_get("platform_specific.packages")
        )
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

    def _prepare_grub_boot_tree(self, chroot_root: Path) -> None:
        """Generate GRUB configuration inside the active rootfs before ISO creation."""
        # 1. Pass the Root Device ID to the bootloader configurator.
        root_device_id = self._system_config().get("root_device_id", "/dev/disk/by-uuid/ARCH_BUILDER_ISO")
        bootloader = Grub2Bootloader(self.config, root_device_id)
        if not bootloader.prepare_files(chroot_root):
            raise ISOBuilderError("Failed to generate GRUB boot configuration.")

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

    def build_bootloaders(self, mountpoint: str) -> None:
        binaries = self._system_config().get("binaries", {})
        source_dir = "/boot"
        effective_root = Path(mountpoint).parent
        staging_root: Optional[Path] = None

        chroot_manager = getattr(self.toolchain, "chroot_manager", None)
        chroot_root = getattr(chroot_manager, "chroot_path", None)
        if chroot_root:
            chroot_root_path = Path(chroot_root)
            try:
                Path(mountpoint).resolve().relative_to(chroot_root_path.resolve())
                effective_root = chroot_root_path
            except Exception:
                effective_root = Path(mountpoint).parent

        if effective_root:
            staging_root = self._prepare_grub_iso_root(effective_root)
            if getattr(self.toolchain, "use_host", True):
                source_dir = str(staging_root)
            else:
                source_dir = "/tmp/arch-builder-iso-root"

        self.logger.info(
            f"[build_bootloaders] Using GRUB source tree '{source_dir}' (mountpoint={mountpoint}, effective_root={effective_root}, staging_root={staging_root})"
        )

        command = [
            binaries.get("grub-mkrescue") or binaries.get("grub_mkrescue") or "grub-mkrescue",
            "-o",
            "/tmp/bootloader-rescue.iso",
            source_dir,
        ]
        self.logger.debug(
            f"[build_bootloaders] Generating bootloaders in {mountpoint} with command: {' '.join(command)}"
        )
        self._run_command(command)
        self.logger.info("Bootloader configured successfully.")

    def finalize_isofile(self, output_path: str) -> None:
        chroot_manager = getattr(self.toolchain, "chroot_manager", None)
        if chroot_manager and getattr(chroot_manager, "chroot_path", None):
            rescue_iso = Path(chroot_manager.chroot_path) / "tmp" / "bootloader-rescue.iso"
            if rescue_iso.exists():
                destination = resolve_from_project(output_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rescue_iso, destination)
                self.logger.info(f"ISO exported from isolated chroot to {destination}")
                return

        binaries = self._system_config().get("binaries", {})
        command = [binaries.get("genisomake") or binaries.get("genisoimage") or "genisoimage", output_path]
        self.logger.info(f"Packaging final image at {output_path}")
        self._run_command(command)
        self.logger.info("ISO created successfully.")

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

