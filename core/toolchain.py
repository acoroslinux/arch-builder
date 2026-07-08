"""
Toolchain Manager (Build Environment)
=====================================
Manages a secondary chroot environment where build tools
(pacman, mksquashfs, xorriso, mtools) are executed.
This avoids polluting the host operating system and helps ensure
reproducibility across any Linux distribution.
"""

import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Toolchain")

class ToolchainManager:
    def __init__(
        self,
        workdir_base: Path,
        mode: str = "mock",
        force_isolated: bool = False,
        pacman_retries: int = 3,
        diagnostics_enabled: bool = False,
        diagnostics_log_path: Optional[Path] = None,
        pacman_cache_dir: Optional[Path] = None,
    ):
        self.mode = mode
        self.force_isolated = force_isolated
        self.pacman_retries = max(1, pacman_retries)
        self.diagnostics_enabled = diagnostics_enabled
        self.diagnostics_log_path = diagnostics_log_path
        self.toolchain_dir = workdir_base / "build_host"
        default_cache = self.toolchain_dir.parent.parent.parent / "cache" / "pacman" / "pkg"
        self.pacman_cache_dir = pacman_cache_dir or default_cache
        self._is_ready = False
        self.use_host = True
        self.build_chroot: Optional[Path] = None
        self.iso_rootfs_path: Optional[Path] = None
        self._mounted = False
        self._diag_fallback_warned = False
        self._cache_mounted = False

    def _diag(self, message: str) -> None:
        if not self.diagnostics_enabled:
            return

        log_path = self.diagnostics_log_path or (self.toolchain_dir / "toolchain-debug.log")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
        line = f"[{timestamp}] {message}\n"

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(line)
            return
        except PermissionError:
            fallback = self.toolchain_dir / "toolchain-debug.log"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            with open(fallback, "a", encoding="utf-8") as fh:
                fh.write(line)

            if not self._diag_fallback_warned:
                logger.warning(
                    "[TOOLCHAIN] Could not write diagnostics log to '%s'. "
                    "Falling back to '%s'.",
                    log_path,
                    fallback,
                )
                self._diag_fallback_warned = True

    def setup(self):
        """
        Ensure the tool environment is ready.
        In a real scenario without the required host tools, this would download
        an ``archlinux-bootstrap.tar.gz`` archive and extract it into
        ``self.toolchain_dir``.
        """
        logger.info(
            f"[TOOLCHAIN] Initializing isolated build host at: {self.toolchain_dir}"
        )
        self.toolchain_dir.mkdir(parents=True, exist_ok=True)
        self._diag(f"setup start mode={self.mode} force_isolated={self.force_isolated}")

        if self.mode == "real":
            if self.force_isolated:
                logger.info(
                    "[TOOLCHAIN] Forced isolated mode enabled. Bootstrapping an isolated chroot..."
                )
                self.use_host = False
                self._bootstrap_archlinux()
                self._is_ready = True
                return

            # Check whether the required tools already exist on the host.
            if self._host_has_tools():
                logger.info(
                    "[TOOLCHAIN] Required tools found on the host. Using the local environment."
                )
                self.use_host = True
            else:
                logger.info(
                    "[TOOLCHAIN] Missing host tools. Bootstrapping an isolated chroot..."
                )
                self.use_host = False
                self._bootstrap_archlinux()

        self._is_ready = True

    def _host_has_tools(self) -> bool:
        required = [
            "mksquashfs",
            "xorriso",
            "pacman",
            "grub-mkrescue",
            "genisoimage",
        ]
        for tool in required:
            if subprocess.run(["which", tool], capture_output=True).returncode != 0:
                return False
        return True

    def _bootstrap_archlinux(self):
        """
        Download and extract the Arch Linux bootstrap to create an isolated
        build host.
        """
        bootstrap_url = "https://mirror.rackspace.com/archlinux/iso/latest/archlinux-bootstrap-x86_64.tar.zst"
        tarball = self.toolchain_dir.parent / "archlinux-bootstrap.tar.zst"

        if tarball.exists() and tarball.stat().st_size == 0:
            tarball.unlink()

        if not tarball.exists():
            logger.info(f"[TOOLCHAIN] Downloading Arch Linux bootstrap: {bootstrap_url}")
            self._diag(f"download bootstrap {bootstrap_url} -> {tarball}")
            subprocess.run(
                ["curl", "-L", "-o", str(tarball), bootstrap_url], check=True
            )

        rootfs_dir = self.toolchain_dir / "root.x86_64"
        if rootfs_dir.exists():
            # Unmount project root and other mounts first to prevent recursive deletion of host project files!
            from core.path_utils import project_root
            proj_root = project_root().resolve()
            chroot_proj_root = rootfs_dir / proj_root.relative_to("/")
            if chroot_proj_root.exists():
                try:
                    self._run_privileged(["umount", "-l", str(chroot_proj_root)], check=False)
                except Exception:
                    pass

            for mount_name in ["var/cache/pacman/pkg", "dev", "sys", "proc"]:
                target = rootfs_dir / mount_name
                if target.exists():
                    try:
                        self._run_privileged(["umount", "-R", "-l", str(target)], check=False)
                    except Exception:
                        pass

            shutil.rmtree(rootfs_dir, ignore_errors=True)

        logger.info("[TOOLCHAIN] Extracting bootstrap tarball...")
        self._diag(f"extract bootstrap tarball into {self.toolchain_dir}")
        subprocess.run(
            [
                "tar",
                "-I",
                "zstd",
                "-xf",
                str(tarball),
                "-C",
                str(self.toolchain_dir),
            ],
            check=True,
        )

        # Create airootfs directory inside the extracted rootfs for package installation
        airootfs_dir = rootfs_dir / "airootfs"
        if not airootfs_dir.exists():
            logger.info("[TOOLCHAIN] Creating airootfs directory in bootstrap rootfs")
            (rootfs_dir / "airootfs").mkdir(parents=True, exist_ok=True)

        # The extracted directory will be self.toolchain_dir / "root.x86_64".
        self.build_chroot = rootfs_dir

        # Mount the required filesystems and initialize pacman.
        self._mount_chroot()

        # Reuse package cache outside chroot to speed up subsequent runs.
        self._mount_pacman_cache()

        # Ensure networking works from within the chroot package manager.
        host_resolv = Path("/etc/resolv.conf")
        chroot_resolv = self.build_chroot / "etc" / "resolv.conf"
        if host_resolv.exists():
            chroot_resolv.parent.mkdir(parents=True, exist_ok=True)
            if chroot_resolv.exists() or chroot_resolv.is_symlink():
                chroot_resolv.unlink(missing_ok=True)
            subprocess.run(["cp", str(host_resolv), str(chroot_resolv)], check=True)
            self._diag("copied host resolv.conf into isolated chroot")

        self._prepare_mirrorlist()
        self._prepare_pacman_config()

        logger.info("[TOOLCHAIN] Initializing pacman-key in the build host...")
        self._run_tool_with_retry(["pacman-key", "--init"], attempts=self.pacman_retries)
        self._run_tool_with_retry(
            ["pacman-key", "--populate", "archlinux"],
            attempts=self.pacman_retries,
        )

        # Install the required toolchain packages.
        logger.info(
            "[TOOLCHAIN] Installing archiso, squashfs-tools, xorriso, and mtools in the build host..."
        )
        self._run_tool_with_retry(
            [
                "pacman",
                "-Sy",
                "--needed",
                "--noconfirm",
                "--cachedir",
                "/var/cache/pacman/pkg",
                "archiso",
                "squashfs-tools",
                "xorriso",
                "mtools",
                "grub",
                "cdrtools",
            ],
            attempts=self.pacman_retries,
        )

    def _prepare_mirrorlist(self) -> None:
        if not self.build_chroot:
            raise RuntimeError("Build chroot path not initialized.")

        mirrorlist_path = self.build_chroot / "etc" / "pacman.d" / "mirrorlist"
        mirrorlist_path.parent.mkdir(parents=True, exist_ok=True)

        mirrorlist = (
            "Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch\n"
            "Server = https://mirrors.kernel.org/archlinux/$repo/os/$arch\n"
            "Server = https://mirror.leaseweb.net/archlinux/$repo/os/$arch\n"
            "Server = https://mirror.osbeck.com/archlinux/$repo/os/$arch\n"
            "Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch\n"
        )
        mirrorlist_path.write_text(mirrorlist, encoding="utf-8")
        self._diag(f"mirrorlist prepared at {mirrorlist_path}")

    def _prepare_pacman_config(self) -> None:
        """Patch pacman.conf in isolated chroot for reusable cache and stable non-interactive operation."""
        if not self.build_chroot:
            raise RuntimeError("Build chroot path not initialized.")

        pacman_conf_path = self.build_chroot / "etc" / "pacman.conf"
        if not pacman_conf_path.exists():
            self._diag(f"pacman.conf missing at {pacman_conf_path}")
            return

        content = pacman_conf_path.read_text(encoding="utf-8")

        # Disable disk-space checks inside chroot bootstrap to avoid false negatives
        # when / is not represented as a dedicated mountpoint in the current namespace.
        content = re.sub(r"(?m)^\s*CheckSpace\s*$", "", content)

        # Avoid aggressive throughput timeout failures on slower mirrors/network links.
        content = re.sub(r"(?m)^\s*DisableDownloadTimeout\s*$", "", content)

        # Remove any pre-existing CacheDir directives; we set a single deterministic one.
        content = re.sub(r"(?m)^\s*CacheDir\s*=.*$", "", content)

        if "[options]" in content:
            content = content.replace(
                "[options]",
                "[options]\nCacheDir = /var/cache/pacman/pkg\nDisableDownloadTimeout",
                1,
            )
        else:
            content = (
                "[options]\n"
                "CacheDir = /var/cache/pacman/pkg\n\n"
                "DisableDownloadTimeout\n\n"
                + content
            )

        # Normalize blank lines left by directive removal.
        content = re.sub(r"\n{3,}", "\n\n", content)
        pacman_conf_path.write_text(content, encoding="utf-8")
        self._diag("pacman.conf patched: CacheDir set and CheckSpace disabled")

    def _run_tool_with_retry(self, command: list, attempts: int) -> subprocess.CompletedProcess:
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                self._diag(f"attempt {attempt}/{attempts}: {' '.join(command)}")
                return self.run_tool(command)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"[TOOLCHAIN] Attempt {attempt}/{attempts} failed for: {' '.join(command)}"
                )
                self._diag(f"attempt {attempt}/{attempts} failed: {exc}")

                if attempt < attempts and command and command[0] == "pacman":
                    try:
                        self.run_tool(
                            [
                                "pacman",
                                "-Syy",
                                "--noconfirm",
                                "--cachedir",
                                "/var/cache/pacman/pkg",
                            ]
                        )
                        self._diag("pacman database refresh succeeded after failure")
                    except Exception as refresh_exc:
                        self._diag(f"pacman database refresh failed: {refresh_exc}")

        if last_error:
            raise last_error
        raise RuntimeError("Command retry loop exited unexpectedly.")

    def _mount_chroot(self):
        if not self.build_chroot:
            raise RuntimeError("Build chroot path not initialized.")

        # Mount proc, sys, and dev inside the build chroot.
        for fs in ["proc", "sys", "dev"]:
            target = self.build_chroot / fs
            target.mkdir(exist_ok=True)
            self._run_privileged(["mount", "--rbind", f"/{fs}", str(target)])
            self._run_privileged(["mount", "--make-rslave", str(target)])

        # Mount the project root directory inside the build chroot.
        from core.path_utils import project_root
        proj_root = project_root().resolve()
        chroot_proj_root = self.build_chroot / proj_root.relative_to("/")
        chroot_proj_root.mkdir(parents=True, exist_ok=True)
        self._run_privileged(["mount", "--bind", str(proj_root), str(chroot_proj_root)])

        self._mounted = True

    def _mount_pacman_cache(self) -> None:
        if not self.build_chroot:
            raise RuntimeError("Build chroot path not initialized.")

        host_cache = self.pacman_cache_dir
        chroot_cache = self.build_chroot / "var" / "cache" / "pacman" / "pkg"

        host_cache.mkdir(parents=True, exist_ok=True)
        chroot_cache.mkdir(parents=True, exist_ok=True)

        self._run_privileged(["mount", "--bind", str(host_cache), str(chroot_cache)])
        self._cache_mounted = True
        self._diag(f"pacman cache bind-mounted host={host_cache} chroot={chroot_cache}")

    def _umount_chroot(self):
        if not self._mounted or not self.build_chroot:
            return

        if self._cache_mounted:
            cache_target = self.build_chroot / "var" / "cache" / "pacman" / "pkg"
            try:
                self._run_privileged(["umount", "-l", str(cache_target)], check=False)
            except Exception:
                pass
            self._cache_mounted = False

        # Unmount project root
        from core.path_utils import project_root
        proj_root = project_root().resolve()
        chroot_proj_root = self.build_chroot / proj_root.relative_to("/")
        try:
            self._run_privileged(["umount", "-l", str(chroot_proj_root)], check=False)
        except Exception:
            pass

        for fs in ["dev", "sys", "proc"]:
            target = self.build_chroot / fs
            try:
                self._run_privileged(["umount", "-R", "-l", str(target)], check=False)
            except Exception:
                pass
        self._mounted = False

    def _run_privileged(self, command: list, check: bool = True) -> subprocess.CompletedProcess:
        """Execute commands that require root, using sudo when needed."""
        full_command = command if os.geteuid() == 0 else ["sudo", *command]
        self._diag(f"privileged command: {' '.join(full_command)}")
        if check:
            return subprocess.run(full_command, check=True)

        # For best-effort cleanup calls (umount), suppress expected stderr noise.
        return subprocess.run(
            full_command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def run_tool(self, command: list, cwd: Path = None) -> subprocess.CompletedProcess:
        """
        Execute a build tool.
        If the tools are available on the host, run the command directly.
        Otherwise, execute it inside the isolated build chroot.
        """
        logger.info(f"[TOOLCHAIN] Running: {' '.join(command)}")
        self._diag(f"run_tool command: {' '.join(command)}")
        if self.mode == "mock":
            logger.info("[TOOLCHAIN] [MOCK] Command simulated successfully.")
            self._diag("run_tool mock execution success")
            return subprocess.CompletedProcess(
                args=command, returncode=0, stdout="", stderr=""
            )

        try:
            if getattr(self, "use_host", True):
                result = subprocess.run(
                    command,
                    check=True,
                    cwd=str(cwd) if cwd else None,
                    text=True,
                    capture_output=True,
                )
            else:
                # Run the command inside the build chroot.
                chroot_cmd = ["chroot", str(self.build_chroot)] + command
                if os.geteuid() != 0:
                    chroot_cmd = ["sudo", *chroot_cmd]
                result = subprocess.run(
                    chroot_cmd,
                    check=True,
                    cwd=str(cwd) if cwd else None,
                    text=True,
                    capture_output=True,
                )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            self._diag(
                "command success"
                + (f"\nSTDOUT:\n{stdout}" if stdout else "")
                + (f"\nSTDERR:\n{stderr}" if stderr else "")
            )
            return result
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip() if hasattr(e, "stderr") else ""
            stdout = (e.stdout or "").strip() if hasattr(e, "stdout") else ""
            details = f"\nSTDERR:\n{stderr}" if stderr else ""
            if stdout:
                details += f"\nSTDOUT:\n{stdout}"
            logger.error(f"[TOOLCHAIN] Command execution failed: {e}{details}")
            self._diag(f"command failed: {e}{details}")
            raise

    def run_command(self, command: list, chroot_path: str = None) -> str:
        """Compatibility wrapper expected by ISOBuilder/BaseEngine."""
        cwd = Path(chroot_path) if chroot_path else None
        result = self.run_tool(command, cwd=cwd)
        return result.stdout or ""

    def execute_command(self, command: list, chroot_path: str = None) -> str:
        """Backward-compatible command runner alias."""
        return self.run_command(command, chroot_path=chroot_path)

    def cleanup(self) -> None:
        """Release mounts created for isolated build hosts."""
        if self.mode == "real" and not self.use_host:
            self._umount_chroot()

