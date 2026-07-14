"""
Build Orchestrator - The Build Workflow Conductor
=================================================
Coordinates all arch-builder components to run the complete
ISO build process.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.chroot_manager import ChrootError, ChrootManager
from core.config_loader import ConfigLoader
from core.iso_engine import Config, ISOBuilder, ISOBuilderError
from core.path_utils import resolve_from_project
from core.toolchain import ToolchainManager


class BuildOrchestratorError(Exception):
    """Exception raised for build orchestration failures."""

    pass


class BuildOrchestrator:
    """
    Coordinates the build workflow.
    It ties together configuration, the architecture engine, and the chroot environment.
    """

    def __init__(
        self,
        arch: str,
        config_path: str,
        mode: str = "mock",
        clean: bool = True,
        force_isolated_toolchain: bool = False,
        toolchain_debug: bool = False,
        toolchain_debug_log: Optional[str] = None,
        toolchain_pacman_retries: int = 3,
        desktop: Optional[str] = None,
        kernel: Optional[str] = None,
        bootloader: Optional[str] = None,
        package_profiles: Optional[List[str]] = None,
        service_profiles: Optional[List[str]] = None,
        live_profile: Optional[str] = None,
        live_user: Optional[str] = None,
        live_groups: Optional[List[str]] = None,
    ):
        """
        Args:
            arch: Target architecture (for example, 'x86_64').
            config_path: Path to the configuration file (for example, 'configs/global_build.json').
            mode: 'mock' or 'real' execution mode for the ChrootManager.
            desktop: Desktop profile to load (for example, 'gnome').
            kernel: Kernel profile or package name to apply.
            bootloader: Bootloader profile name to apply.
            package_profiles: Optional package profile names from configs/packages.
            service_profiles: Optional common service profile names from configs/services.
            live_profile: Live user profile from configs/live-users.
            live_user: Override live ISO username.
            live_groups: Override live ISO user groups.
        """
        self.arch = (arch or "x86_64").lower()
        if self.arch not in ("x86_64", "x86-64"):
            raise BuildOrchestratorError(f"Architecture '{self.arch}' is not supported. Only x86_64 is supported.")
        self.arch = "x86_64"
        self.config_path = str(resolve_from_project(config_path))
        self.mode = mode
        self.clean = clean
        self.force_isolated_toolchain = force_isolated_toolchain
        self.toolchain_debug = toolchain_debug
        self.toolchain_debug_log = toolchain_debug_log
        self.toolchain_pacman_retries = toolchain_pacman_retries
        self.desktop = desktop
        self.kernel = kernel
        self.bootloader = bootloader
        self.package_profiles = package_profiles or []
        self.service_profiles = service_profiles or []
        self.live_profile = live_profile
        self.live_user = live_user
        self.live_groups = live_groups or []

        # Components
        self.config_loader = ConfigLoader()
        self.builder: Optional[ISOBuilder] = None
        self.chroot: Optional[ChrootManager] = None
        self.toolchain: Optional[ToolchainManager] = None
        self.workdir: Optional[Path] = None

    def _resolve_writable_workdir(self, base_workdir: Path) -> Path:
        """Return a writable workdir path, falling back if needed."""
        preferred = base_workdir / self.arch
        fallback = resolve_from_project(Path("arch-builder") / "fallback" / self.arch)
        temp_fallback = Path(tempfile.gettempdir()) / "arch-builder-fallback" / self.arch

        for candidate in (preferred, fallback, temp_fallback):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                probe = candidate / ".write_test"
                probe.write_text("ok")
                probe.unlink(missing_ok=True)
                if candidate != preferred:
                    print(
                        f"[ORCHESTRATOR] Workdir fallback active: {candidate}"
                    )
                return candidate
            except Exception:
                continue

        raise BuildOrchestratorError(
            f"No writable workdir available (checked: {preferred} and {fallback})."
        )

    def _setup(self):
        """Initialize the core build components."""
        print(f"\n[ORCHESTRATOR] Starting build workflow for {self.arch}...")
        if self.desktop:
            print(f"[ORCHESTRATOR] Desktop profile: {self.desktop}")
        if self.kernel:
            print(f"[ORCHESTRATOR] Kernel selection: {self.kernel}")
        if self.bootloader:
            print(f"[ORCHESTRATOR] Bootloader selection: {self.bootloader}")
        if self.package_profiles:
            print(
                f"[ORCHESTRATOR] Package profiles: {', '.join(self.package_profiles)}"
            )
        if self.service_profiles:
            print(
                f"[ORCHESTRATOR] Service profiles: {', '.join(self.service_profiles)}"
            )
        if self.live_profile:
            print(f"[ORCHESTRATOR] Live profile: {self.live_profile}")
        if self.live_user:
            print(f"[ORCHESTRATOR] Live user override: {self.live_user}")
        if self.live_groups:
            print(
                f"[ORCHESTRATOR] Live user groups: {', '.join(self.live_groups)}"
            )

        # 1. Load and validate configuration using the assembler.
        from core.config_loader import ConfigAssembler

        assembler = ConfigAssembler(str(Path(self.config_path).parent))
        try:
            self.config = assembler.assemble(
                target_arch=self.arch,
                target_desktop=self.desktop,
                target_kernel=self.kernel,
                target_bootloader=self.bootloader,
                package_profiles=self.package_profiles,
                service_profiles=self.service_profiles,
                target_live_profile=self.live_profile,
                live_user=self.live_user,
                live_groups=self.live_groups,
            )
        except Exception as e:
            raise BuildOrchestratorError(f"Failed to load configuration: {e}")

        if not self.config:
            raise BuildOrchestratorError("The generated configuration is null or invalid.")

        # 2. Initialize the chroot manager first.
        # Use the base workdir defined in config for the target architecture.
        configured_base = self.config.get("system.workdir_base", "arch-builder/workdir")
        base_workdir = resolve_from_project(str(configured_base))
        workdir = self._resolve_writable_workdir(base_workdir)

        # Clean previous build artifacts before starting a new build.
        # Keep persistent caches managed outside these folders.
        if self.clean:
            # Clean both legacy paths (airootfs) and toolchain paths (build_host/*)
            stale_paths = [
                workdir / "airootfs",
                workdir / "mnt",
                workdir / "build-output",
                workdir / "build_host",
            ]
            for stale_dir in stale_paths:
                if stale_dir.exists():
                    shutil.rmtree(stale_dir, ignore_errors=True)

        # The chroot manager uses the rootfs inside the workdir.
        chroot_path = workdir / "airootfs"
        self.chroot = ChrootManager(chroot_path=chroot_path, mode=self.mode, arch=self.arch)

        # 3. Prepare a build toolchain (host tools or isolated Arch bootstrap in real mode).
        force_isolated = self.force_isolated_toolchain or bool(
            self.config.get("system.force_isolated_toolchain", False)
        )
        pacman_retries = int(
            self.config.get("system.toolchain_pacman_retries", self.toolchain_pacman_retries)
        )
        diagnostics_enabled = self.toolchain_debug or bool(
            self.config.get("system.toolchain_debug", False)
        )
        diagnostics_log = self.toolchain_debug_log or self.config.get(
            "system.toolchain_debug_log"
        )
        pacman_cache_dir = self.config.get("system.toolchain_pacman_cache_dir")
        diagnostics_log_path = (
            resolve_from_project(diagnostics_log)
            if diagnostics_log
            else workdir / "toolchain-debug.log"
        )
        pacman_cache_path = (
            resolve_from_project(pacman_cache_dir)
            if pacman_cache_dir
            else resolve_from_project("arch-builder/cache/pacman/pkg")
        )

        if diagnostics_enabled:
            print(f"[ORCHESTRATOR] Toolchain diagnostics log: {diagnostics_log_path}")

        self.toolchain = ToolchainManager(
            workdir_base=workdir,
            mode=self.mode,
            force_isolated=force_isolated,
            pacman_retries=pacman_retries,
            diagnostics_enabled=diagnostics_enabled,
            diagnostics_log_path=diagnostics_log_path,
            pacman_cache_dir=pacman_cache_path,
            arch=self.arch,
        )
        if self.chroot:
            self.chroot.toolchain = self.toolchain
        try:
            self.toolchain.setup()
        except Exception as e:
            raise BuildOrchestratorError(f"Failed to setup build toolchain: {e}")

        # In real isolated mode, the bootstrap provides pacman and other tools,
        # but ISO packages must be installed into a separate airootfs to avoid
        # conflicts with the toolchain packages already in the bootstrap.
        if self.mode == "real" and not getattr(self.toolchain, "use_host", True):
            toolchain_chroot = getattr(self.toolchain, "build_chroot", None)
            iso_rootfs = Path(toolchain_chroot) / "airootfs" if toolchain_chroot else None
            if toolchain_chroot and Path(toolchain_chroot).exists() and iso_rootfs:
                print(
                    f"[ORCHESTRATOR] Using isolated build host: {toolchain_chroot}"
                )
                # Ensure the ISO rootfs exists with proper structure
                iso_rootfs.mkdir(parents=True, exist_ok=True)
                # Create essential directories for the ISO rootfs
                for subdir in ["etc", "var", "usr", "boot", "opt", "srv"]:
                    (iso_rootfs / subdir).mkdir(exist_ok=True)
                
                # Configure the toolchain to know about the separate ISO rootfs
                self.toolchain.iso_rootfs_path = iso_rootfs
                # Update the chroot manager to use the ISO rootfs and have access to toolchain
                self.chroot = ChrootManager(
                    chroot_path=iso_rootfs,
                    mode=self.mode,
                    toolchain=self.toolchain,
                    arch=self.arch,
                )

        # 4. Initialize ISOBuilder with chroot manager and toolchain injected.
        try:
            self.builder = ISOBuilder(
                arch=self.arch,
                config=self.config,
                toolchain=self.toolchain,
                chroot_manager=self.chroot,
            )
            self.workdir = self.builder.engine.setup_workdir()
        except ISOBuilderError as e:
            raise BuildOrchestratorError(f"Failed to initialize the builder: {e}")

    def run_build(self, output_iso: str) -> Path:
        """
        Run the full build pipeline by delegating to the builder.
        """
        try:
            self._setup()

            print("\n[STEP 1/1] Running build pipeline through the engine...")
            output_path = Path(output_iso)
            # ISOBuilder orchestrates the chroot and ISO creation internally.
            result_iso = self.builder.build(output_path, str(self.workdir))

            print("\n✅ BUILD SUCCEEDED!")
            print(f"ISO generated at: {result_iso}")

            return result_iso

        except Exception as e:
            print(f"\n❌ CRITICAL BUILD ERROR: {e}")
            raise BuildOrchestratorError(f"Pipeline failed: {e}")

        finally:
            if self.chroot:
                self.chroot.cleanup()
            if self.toolchain:
                self.toolchain.cleanup()


if __name__ == "__main__":
    # Example manual execution for local testing.
    orchestrator = BuildOrchestrator(
        arch="x86_64", config_path=str(resolve_from_project("configs/global_build.json")), mode="mock"
    )
    try:
        orchestrator.run_build("my_arch_custom.iso")
    except Exception as e:
        print(f"Test run failed: {e}")