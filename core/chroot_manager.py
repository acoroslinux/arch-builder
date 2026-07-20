# -*- coding: utf-8 -*-
"""
core/chroot_manager.py

Centralised management of the chroot environment (mock or real).

This module provides:
*   Mock filesystem handling for unit‑testing and development.
*   A ChrootManager that can switch between mock and real modes.
*   Integration with the central logging system (core.logger_setup).
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ----------------------------------------------------------------------
# Import the central logger configuration
# ----------------------------------------------------------------------
try:
    from .logger_setup import setup_logger
except ImportError:  # pragma: no cover
    # Fallback – should never happen in a valid installation
    def setup_logger(*_, **__):  # type: ignore
        import logging

        logging.basicConfig(level=logging.INFO)
        return logging.getLogger()

# ----------------------------------------------------------------------
# Mock filesystem handler – simulates file operations for tests
# ----------------------------------------------------------------------
class ChrootManagerError(Exception):
    """Raised when chroot lifecycle or command execution fails."""

    pass

class ChrootError(ChrootManagerError):
    """Backward-compatible alias for older imports."""

    pass

class MockFSHandler:
    """Simulates a minimal filesystem inside the chroot directory."""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)

    def create_file(self, path: str, content: str) -> None:
        """Simulate creating a file – logs the operation."""
        full_path = os.path.join(self.base_dir, path)
        parent = os.path.dirname(full_path)

        if not parent.startswith(self.base_dir):
            raise ValueError("Path outside the simulated scope.")

        # Use the central logger to record the action
        logging.getLogger("chroot").debug(
            f"[MOCK FS] Simulated file created at: {path} ({len(content)} bytes)"
        )

    def read_file(self, path: str) -> Optional[str]:
        """Simulate reading a file – logs the operation."""
        if "template" in path:
            # Return a dummy template content for testing
            return f"# Simulated template content for {path}\n# Line 1\n{os.urandom(10).hex()}\n"
        logging.getLogger("chroot").debug(f"[MOCK FS] Simulated read from {path}")
        return None

    def list_directory(self, path: str) -> List[str]:
        """Simulate directory listing – used by tests."""
        if "etc/fstab" in path:
            return ["/dev/sda1", "swap"]
        return ["file1.conf", "subdir/", "readme.txt"]

# ----------------------------------------------------------------------
# Main ChrootManager – controls mock/real mode and command execution
# ----------------------------------------------------------------------
class ChrootManager:
    """
    Manages a chroot environment that can operate in two modes:
    *   Mock mode – pure Python simulation (no external processes).
    *   Real mode – spawns subprocesses with sudo/chroot (requires privileges).
    """

    def __init__(
        self,
        workdir: Optional[str] = None,
        chroot_path: Optional[Path] = None,
        mode: str = "mock",
        chroot_mode: Optional[bool] = None,
        toolchain: Optional[Any] = None,
        arch: Optional[str] = None,
    ):
        base_path = chroot_path or workdir
        if base_path is None:
            raise ChrootManagerError("A workdir or chroot_path must be provided.")

        self._workdir = os.path.abspath(str(base_path))
        self.chroot_path = Path(self._workdir)
        self.mode = mode
        self.chroot_mode = chroot_mode
        self.is_mock = mode != "real"
        self.fs_handler = MockFSHandler(self._workdir)
        self.toolchain = toolchain
        self.arch = (arch or "x86_64").lower()
        if self.arch not in ("x86_64", "x86-64"):
            raise ChrootManagerError(f"Architecture '{self.arch}' is not supported. Only x86_64 is supported.")
        self.arch = "x86_64"

        # Each manager gets its own logger (useful for debugging)
        self.logger = setup_logger("chroot", "chroot.log", logging.INFO)

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------
    def set_real_mode(self) -> None:
        """Switch from mock to real execution – requires sudo etc."""
        if self.is_mock:
            logging.getLogger("chroot").warning(
                "[WARN] ChrootManager switching to REAL MODE. "
                "This requires elevated privileges (sudo) and a complete Linux environment."
            )
            self.is_mock = False
            self.mode = "real"

    # ------------------------------------------------------------------
    # Basic chroot lifecycle
    # ------------------------------------------------------------------
    def setup(self) -> str:
        """Prepare the basic directory structure of the chroot."""
        if self.is_mock:
            self.logger.info("[setup] Preparing directory structure virtually.")
            return self._workdir

        try:
            os.makedirs(self._workdir, exist_ok=True)
            self.logger.critical(
                f"[setup] Chroot base directory created at {self._workdir}"
            )
            return self._workdir
        except Exception as e:
            raise ChrootManagerError(
                f"Failed to create real chroot directories: {e}. Check permissions (sudo)."
            )

    def cleanup(self) -> None:
        """Compatibility no-op used by the orchestrator in mock mode."""
        self.logger.info("[cleanup] Chroot cleanup completed.")

    # ------------------------------------------------------------------
    # Command execution – mock or real
    # ------------------------------------------------------------------
    def run_command(
        self, command: Union[List[str], str], chroot_path: Optional[str] = None
    ) -> str:
        """
        Execute a command either in mock mode (simple logging) or real mode
        (spawn a subprocess inside the chroot). Returns stdout.
        """
        if isinstance(command, str):
            command_list = ["sh", "-lc", command]
            cmd_str = command
        else:
            command_list = command
            cmd_str = " ".join(command)

        if self.is_mock:
            # Mock mode – just log the intent
            logging.getLogger("chroot").debug(
                f"[run_command] Simulated execution: {cmd_str}"
            )
            return f"Simulated output for command: {command_list[0]}"

        # Real mode – spawn a subprocess inside the chroot
        try:
            effective_chroot = chroot_path or self._workdir
            if effective_chroot and os.path.isdir(effective_chroot):
                # Ensure networking/DNS resolution works inside the chroot
                host_resolv = Path("/etc/resolv.conf")
                target_resolv = Path(effective_chroot) / "etc" / "resolv.conf"
                copied_resolv = False
                
                # Copy host resolv.conf if not already present in the chroot
                if host_resolv.exists() and not target_resolv.exists():
                    try:
                        target_resolv.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(host_resolv, target_resolv)
                        copied_resolv = True
                    except Exception as e:
                        logging.getLogger("chroot").warning(f"Could not copy resolv.conf to chroot: {e}")

                try:
                    # Execute directly through chroot with argument-safe process invocation.
                    full_command = ["sudo", "chroot", effective_chroot, *command_list]
                    logging.getLogger("chroot").info(
                        f"[run_command] Executing command inside chroot: {cmd_str}"
                    )
                    result = subprocess.run(
                        full_command, capture_output=True, check=True, text=True
                    )
                    logging.getLogger("chroot").info(
                        f"[run_command] Command '{cmd_str}' executed successfully inside chroot."
                    )
                    return result.stdout
                finally:
                    # Clean up the copied resolv.conf to avoid baking host DNS into the ISO
                    if copied_resolv:
                        try:
                            target_resolv.unlink(missing_ok=True)
                        except Exception:
                            pass
            else:
                raise PermissionError(
                    "Chroot environment is unavailable or misconfigured on the host."
                )
        except subprocess.CalledProcessError as e:
            output_details = []
            if e.stdout and e.stdout.strip():
                output_details.append(f"STDOUT:\n{e.stdout.strip()}")
            if e.stderr and e.stderr.strip():
                output_details.append(f"STDERR:\n{e.stderr.strip()}")
            details_str = "\n".join(output_details) if output_details else "No output details available."
            error_msg = f"Failed to execute command '{command_list[0]}'. Error status:\n{details_str}"
            logging.getLogger("chroot").error(error_msg)
            raise ChrootManagerError(error_msg)
        except Exception as e:
            raise ChrootManagerError(
                f"Unexpected error during chroot execution: {type(e).__name__}: {str(e)}"
            )

    # ------------------------------------------------------------------
    # Package installation – uses the chroot manager's run_command
    # ------------------------------------------------------------------
    def _normalize_package_plan(
        self, packages: Union[List[str], Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Normalize legacy package list or structured package plan into a single format."""
        if isinstance(packages, dict):
            official = [str(p) for p in packages.get("official", [])]
            aur = [str(p) for p in packages.get("aur", [])]
            local_paths = [str(p) for p in packages.get("local_paths", [])]
            return {
                "official": official,
                "aur": aur,
                "local_paths": local_paths,
            }

        return {
            "official": [str(p) for p in packages],
            "aur": [],
            "local_paths": [],
        }

    def _install_local_packages_real(self, local_paths: List[str]) -> None:
        if not local_paths:
            return

        use_host = not self.toolchain or getattr(self.toolchain, "use_host", True)

        if use_host:
            if shutil.which("pacman") is None:
                raise ChrootManagerError(
                    "Host pacman is unavailable. Enable an isolated toolchain or install pacman on the host."
                )
            # Host mode: run pacman -U directly on the host targeting the chroot
            command = [
                "sudo",
                "pacman",
                "-U",
                "--noconfirm",
                "--needed",
                "--root",
                str(self._workdir),
                *local_paths,
            ]
            self.logger.info(f"[host] Installing local packages: {' '.join(command)}")
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                raise ChrootManagerError(f"Host pacman -U failed: {e.stderr}")
            return

        run_path = self.toolchain.build_chroot if self.toolchain and getattr(self.toolchain, "build_chroot", None) else self._workdir
        staging_host_dir = Path(run_path) / "tmp" / "custom-packages"
        staging_host_dir.mkdir(parents=True, exist_ok=True)

        iso_rootfs = getattr(self.toolchain, "iso_rootfs_path", None) if self.toolchain else None
        root_flag = ["--root", "/airootfs"] if iso_rootfs else []

        staged_targets: List[str] = []
        for path_str in local_paths:
            src = Path(path_str)
            if not src.exists() or not src.is_file():
                self.logger.warning(f"Skipping missing local package file: {src}")
                continue

            dst = staging_host_dir / src.name
            shutil.copy2(src, dst)
            staged_targets.append(f"/tmp/custom-packages/{src.name}")

        if staged_targets:
            # Install into airootfs when in isolated mode, otherwise into build chroot
            command = ["pacman", "-U", "--noconfirm", *root_flag, *staged_targets]
            self.run_command(command, chroot_path=str(run_path))

    def _install_aur_packages_real(self, aur_packages: List[str]) -> None:
        if not aur_packages:
            return

        use_host = not self.toolchain or getattr(self.toolchain, "use_host", True)

        if use_host:
            if shutil.which("pacman") is None:
                raise ChrootManagerError(
                    "Host pacman is unavailable. Enable an isolated toolchain or install pacman on the host."
                )
            # Prepare build prerequisites on host
            subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm", "git", "base-devel"], check=True)
            
            build_user = os.environ.get("SUDO_USER")
            if not build_user or build_user == "root":
                if subprocess.run(["id", "-u", "aurbuilder"], capture_output=True).returncode != 0:
                    subprocess.run(["sudo", "useradd", "-m", "aurbuilder"], check=True)
                build_user = "aurbuilder"

            # Grant passwordless sudo to aurbuilder on host
            if build_user == "aurbuilder":
                subprocess.run([
                    "sudo", "sh", "-c",
                    "mkdir -p /etc/sudoers.d && echo 'aurbuilder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/aurbuilder"
                ], check=True)

            for pkg in aur_packages:
                if not re.match(r"^[a-zA-Z0-9@._+-]+$", pkg):
                    raise ChrootManagerError(f"Invalid AUR package name: {pkg}")

                # Step 1: Build on host as build_user
                build_dir = Path("/tmp/aur-build") / pkg
                if build_dir.exists():
                    shutil.rmtree(build_dir, ignore_errors=True)
                build_dir.mkdir(parents=True, exist_ok=True)
                
                subprocess.run(["sudo", "chown", "-R", f"{build_user}:{build_user}", "/tmp/aur-build"], check=True)

                build_cmd = (
                    "set -e; "
                    f"cd /tmp/aur-build; "
                    f"git clone https://aur.archlinux.org/{pkg}.git; "
                    f"cd {pkg}; makepkg -s --noconfirm --needed"
                )
                
                # Run the build command as the build_user
                subprocess.run(
                    ["runuser", "-u", build_user, "--", "bash", "-lc", build_cmd],
                    check=True, capture_output=True, text=True
                )

                # Find the built packages
                pkg_files = list(build_dir.glob("*.pkg.tar.zst"))
                if not pkg_files:
                    raise ChrootManagerError(f"No built package files found for {pkg}")

                # Step 2: Install on host first (so subsequent AUR packages can find it as a dependency)
                host_cmd = [
                    "sudo",
                    "pacman",
                    "-U",
                    "--noconfirm",
                    "--needed",
                ] + [str(pf) for pf in pkg_files]
                self.logger.info(f"[host] Installing dependency on host: {' '.join(host_cmd)}")
                subprocess.run(host_cmd, check=True, capture_output=True, text=True)

                # Step 3: Install into the target rootfs using pacman -U on host as root
                target_cmd = [
                    "sudo",
                    "pacman",
                    "-U",
                    "--noconfirm",
                    "--needed",
                    "--root",
                    str(self._workdir),
                ] + [str(pf) for pf in pkg_files]
                self.logger.info(f"[host] Installing package in target rootfs: {' '.join(target_cmd)}")
                subprocess.run(target_cmd, check=True, capture_output=True, text=True)
            return

        # Isolated mode
        run_path = self.toolchain.build_chroot if self.toolchain and getattr(self.toolchain, "build_chroot", None) else self._workdir

        iso_rootfs = getattr(self.toolchain, "iso_rootfs_path", None) if self.toolchain else None
        root_flag = ["--root", "/airootfs"] if iso_rootfs else []

        # Prepare build prerequisites and non-root builder account.
        self.run_command(
            ["pacman", "-S", "--needed", "--noconfirm", "git", "base-devel"],
            chroot_path=str(run_path),
        )
        self.run_command(
            [
                "bash",
                "-lc",
                "id -u aurbuilder >/dev/null 2>&1 || useradd -m aurbuilder",
            ],
            chroot_path=str(run_path),
        )
        # Grant passwordless sudo to aurbuilder so makepkg can install build dependencies
        self.run_command(
            [
                "bash",
                "-lc",
                "mkdir -p /etc/sudoers.d && echo 'aurbuilder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/aurbuilder",
            ],
            chroot_path=str(run_path),
        )

        for pkg in aur_packages:
            # Basic sanitization to avoid command injection.
            if not re.match(r"^[a-zA-Z0-9@._+-]+$", pkg):
                raise ChrootManagerError(f"Invalid AUR package name: {pkg}")

            # Step 1: Build the package as aurbuilder
            build_cmd = (
                "set -e; "
                f"cd /tmp; rm -rf {pkg}; "
                f"git clone https://aur.archlinux.org/{pkg}.git; "
                f"cd {pkg}; makepkg -s --noconfirm --needed"
            )
            self.run_command(
                ["runuser", "-u", "aurbuilder", "--", "bash", "-lc", build_cmd],
                chroot_path=str(run_path),
            )

            # Step 2: Install the built package file(s) into the target rootfs as root.
            # If we are installing into a separate rootfs (isolated mode), we must also
            # install it in the build host so subsequent AUR packages can find it as a dependency.
            if root_flag:
                install_cmd = (
                    "set -e; "
                    f"cd /tmp/{pkg}; "
                    "yes | pacman -U --needed *.pkg.tar.zst; "
                    f"yes | pacman -U --needed {' '.join(root_flag)} *.pkg.tar.zst"
                )
            else:
                install_cmd = (
                    "set -e; "
                    f"cd /tmp/{pkg}; "
                    f"yes | pacman -U --needed *.pkg.tar.zst"
                )
            self.run_command(
                ["bash", "-lc", install_cmd],
                chroot_path=str(run_path),
            )

    def _init_airootfs_pacman(self, run_path: str) -> None:
        """Initialize pacman database and required directories inside airootfs."""
        iso_rootfs = getattr(self.toolchain, "iso_rootfs_path", None) if self.toolchain else None
        if not iso_rootfs:
            return

        # Ensure the airootfs has the required pacman directories
        airootfs_path = Path(run_path) / "airootfs"
        for subdir in ["var/lib/pacman", "var/cache/pacman/pkg", "etc/pacman.d"]:
            (airootfs_path / subdir).mkdir(parents=True, exist_ok=True)

        # Copy pacman config and mirrorlist from the build chroot into airootfs
        build_chroot = Path(run_path)
        for conf_file in ["etc/pacman.conf", "etc/pacman.d/mirrorlist"]:
            src = build_chroot / conf_file
            dst = airootfs_path / conf_file
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        # Ensure the target architecture and mirrors are correctly configured in the target configs
        pacman_conf_dst = airootfs_path / "etc" / "pacman.conf"
        mirrorlist_dst = airootfs_path / "etc" / "pacman.d" / "mirrorlist"
        
        if pacman_conf_dst.exists():
            content = pacman_conf_dst.read_text(encoding="utf-8")
            # Ensure Architecture is set correctly
            expected_arch_line = f"Architecture = {self.arch}"
            if expected_arch_line not in content:
                if re.search(r"(?m)^\s*Architecture\s*=", content):
                    content = re.sub(r"(?m)^\s*Architecture\s*=.*$", expected_arch_line, content)
                elif "[options]" in content:
                    content = content.replace("[options]", f"[options]\n{expected_arch_line}", 1)
            pacman_conf_dst.write_text(content, encoding="utf-8")

        # Copy the target's mirrorlist to the build host chroot's /etc/pacman.d/mirrorlist as well
        if mirrorlist_dst.exists():
            build_host_mirrorlist = build_chroot / "etc" / "pacman.d" / "mirrorlist"
            build_host_mirrorlist.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(mirrorlist_dst, build_host_mirrorlist)

        # Initialize the pacman keyring and database inside airootfs.
        # In isolated mode, the build host has pacman and pacman-key, while the
        # target airootfs only receives the generated keyring directories.
        self.logger.info("[airootfs] Initializing pacman keyring and database in airootfs...")
        try:
            # Use pacman-key from the build host to initialize the gpg directory inside airootfs.
            self.run_command(
                [
                    "pacman-key",
                    "--gpgdir",
                    "/airootfs/etc/pacman.d/gnupg",
                    "--init",
                ],
                chroot_path=str(run_path),
            )
            self.run_command(
                [
                    "pacman-key",
                    "--gpgdir",
                    "/airootfs/etc/pacman.d/gnupg",
                    "--populate",
                    "archlinux",
                ],
                chroot_path=str(run_path),
            )

            # Ensure the airootfs keyring directory was created.
            target_gpgdir = airootfs_path / "etc" / "pacman.d" / "gnupg"
            if not target_gpgdir.exists():
                raise ChrootManagerError(
                    "airootfs pacman keyring directory was not created by pacman-key."
                )

            # Sync package databases for the target root using its pacman.conf.
            self.run_command(
                [
                    "pacman",
                    "--root",
                    "/airootfs",
                    "--config",
                    "/airootfs/etc/pacman.conf",
                    "-Sy",
                ],
                chroot_path=str(run_path),
            )
        except ChrootManagerError as e:
            self.logger.warning(f"[airootfs] pacman initialization in airootfs failed (may be ok): {e}")

    def _install_official_packages_real(self, official_packages: List[str], attempts: int = 3) -> None:
        if not official_packages:
            return

        last_error: Optional[Exception] = None
        use_host = not self.toolchain or getattr(self.toolchain, "use_host", True)

        if use_host:
            if shutil.which("pacman") is None:
                raise ChrootManagerError(
                    "Host pacman is unavailable. Enable an isolated toolchain or install pacman on the host."
                )
            
            # Ensure pacman database directory exists in the target rootfs
            target_path = Path(self._workdir)
            for d in ["var/lib/pacman", "var/cache/pacman/pkg"]:
                (target_path / d).mkdir(parents=True, exist_ok=True)

            # Host mode: run pacman directly on the host targeting the chroot using --root
            
            # Always ensure archlinux-keyring is up to date before installing other packages
            try:
                subprocess.run(
                    ["sudo", "pacman", "-S", "--needed", "--noconfirm", "--root", str(self._workdir), "archlinux-keyring"],
                    check=True, capture_output=True
                )
            except Exception as e:
                self.logger.warning(f"Failed to update archlinux-keyring on host (may be ok): {e}")

            for attempt in range(1, max(1, attempts) + 1):
                try:
                    command = [
                        "sudo",
                        "pacman",
                        "-S",
                        "--needed",
                        "--noconfirm",
                        "--disable-download-timeout",
                        "--root",
                        str(self._workdir),
                        *official_packages,
                    ]
                    self.logger.info(f"[host] Running: {' '.join(command)}")
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    return
                except subprocess.CalledProcessError as e:
                    last_error = e
                    self.logger.warning(
                        f"Host package install attempt {attempt}/{attempts} failed: {e.stderr}"
                    )
                    if attempt < attempts:
                        try:
                            subprocess.run(
                                ["sudo", "pacman", "-Syy", "--noconfirm", "--root", str(self._workdir)],
                                check=True, capture_output=True
                            )
                        except Exception:
                            pass
            if last_error:
                raise ChrootManagerError(f"Host pacman failed: {last_error.stderr}")
            return

        # Isolated mode
        run_path = self.toolchain.build_chroot if self.toolchain and getattr(self.toolchain, "build_chroot", None) else self._workdir

        # Determine if we need to target a separate ISO rootfs (airootfs) instead of
        # the build chroot root. This prevents ISO packages from conflicting with
        # the toolchain packages already installed in the build host.
        iso_rootfs = getattr(self.toolchain, "iso_rootfs_path", None) if self.toolchain else None
        if iso_rootfs:
            root_flag = ["--root", "/airootfs", "--config", "/airootfs/etc/pacman.conf"]
        else:
            root_flag = []

        # Initialize pacman database in airootfs before installing packages
        if iso_rootfs:
            self._init_airootfs_pacman(str(run_path))

        # Always ensure archlinux-keyring is up to date before installing other packages
        try:
            keyring_cmd = ["pacman", "-S", "--needed", "--noconfirm", *root_flag, "archlinux-keyring"]
            self.run_command(keyring_cmd, chroot_path=str(run_path))
        except Exception as e:
            self.logger.warning(f"Failed to update archlinux-keyring (may be ok): {e}")

        for attempt in range(1, max(1, attempts) + 1):
            try:
                # If iso_rootfs is set, use --root to install into airootfs
                # instead of the build chroot root. This keeps ISO packages
                # separate from the build toolchain.
                command = [
                    "pacman",
                    "-S",
                    "--needed",
                    "--noconfirm",
                    "--disable-download-timeout",
                    *root_flag,
                    *official_packages,
                ]
                self.run_command(command, chroot_path=str(run_path))
                return
            except ChrootManagerError as exc:
                last_error = exc
                self.logger.warning(
                    f"Official package install attempt {attempt}/{attempts} failed."
                )
                if attempt < attempts:
                    try:
                        if iso_rootfs:
                            self.run_command(
                                [
                                    "pacman",
                                    "--root",
                                    "/airootfs",
                                    "--config",
                                    "/airootfs/etc/pacman.conf",
                                    "-Syy",
                                    "--noconfirm",
                                    "--disable-download-timeout",
                                ],
                                chroot_path=str(run_path),
                            )
                        else:
                            self.run_command(
                                [
                                    "pacman",
                                    "-Syy",
                                    "--noconfirm",
                                    "--disable-download-timeout",
                                ],
                                chroot_path=str(run_path),
                            )
                    except ChrootManagerError:
                        pass

        if last_error:
            raise last_error

    def _mount_essential_filesystems(self) -> None:
        """Mount /proc, /sys, and /dev inside the chroot path."""
        import subprocess
        import os
        
        self.logger.info("[chroot] Mounting essential filesystems (/proc, /sys, /dev)...")
        mounts = [
            ("/proc", self.chroot_path / "proc", "--bind"),
            ("/sys", self.chroot_path / "sys", "--bind"),
            ("/dev", self.chroot_path / "dev", "--bind"),
        ]
        
        def _sudo_run(cmd, check=True):
            full = cmd if os.geteuid() == 0 else ["sudo", *cmd]
            return subprocess.run(full, check=check, capture_output=True, text=True)

        for src, dst, opts in mounts:
            dst.mkdir(parents=True, exist_ok=True)
            try:
                # Check if already mounted
                with open("/proc/mounts", "r") as f:
                    mounted_paths = [line.split()[1] for line in f.readlines() if len(line.split()) > 1]
                if os.path.abspath(str(dst)) in mounted_paths:
                    self.logger.debug(f"{dst} is already mounted, skipping.")
                    continue
            except Exception:
                pass
            _sudo_run(["mount", opts, str(src), str(dst)], check=False)

        # Mount /dev/shm properly for python multiprocessing
        shm_dst = self.chroot_path / "dev" / "shm"
        shm_dst.mkdir(parents=True, exist_ok=True)
        _sudo_run(["mount", "-t", "tmpfs", "tmpfs", str(shm_dst)], check=False)

    def _unmount_essential_filesystems(self) -> None:
        """Unmount /proc, /sys, and /dev from the chroot path."""
        import subprocess
        import os
        
        self.logger.info("[chroot] Unmounting essential filesystems...")
        mounts = [
            self.chroot_path / "dev" / "shm",
            self.chroot_path / "proc",
            self.chroot_path / "sys",
            self.chroot_path / "dev",
        ]
        
        def _sudo_run(cmd, check=True):
            full = cmd if os.geteuid() == 0 else ["sudo", *cmd]
            return subprocess.run(full, check=check, capture_output=True, text=True)

        # Unmount in reverse order
        for dst in reversed(mounts):
            if dst.exists():
                _sudo_run(["umount", "-l", str(dst)], check=False)

    def install_packages(self, packages: Union[List[str], Dict[str, Any]]) -> None:
        """Install official, local and AUR packages inside the chroot (mock or real)."""
        self.logger.info("Starting package installation with cache management.")
        plan = self._normalize_package_plan(packages)

        if self.is_mock:
            # In mock we just simulate the process
            self.fs_handler.create_file("etc/apk/keys", "MOCK-KEY-DATA")
            logging.getLogger("chroot").debug("[MOCK FS] Simulated keys installed.")
            output = (
                "Packages installed virtually. "
                f"official={plan['official']} aur={plan['aur']} local={plan['local_paths']}\n"
            )
        else:
            # Real mode – install official packages from repos.
            try:
                self._mount_essential_filesystems()
                self._install_official_packages_real(plan["official"], attempts=3)

                # Install local package files placed by the user.
                self._install_local_packages_real(plan["local_paths"])

                # Install AUR packages through makepkg in a dedicated non-root user.
                self._install_aur_packages_real(plan["aur"])
                output = "Package plan applied successfully."
            except ChrootManagerError as e:
                raise RuntimeError(
                    f"Fatal package installation failure in real chroot: {e}"
                )
            finally:
                self._unmount_essential_filesystems()

        self.logger.info("Package installer finished. Status: OK")

    # ------------------------------------------------------------------
    # fstab generation – creates /etc/fstab inside the chroot
    # ------------------------------------------------------------------
    def generate_fstab(self) -> str:
        """Generate a simple /etc/fstab and persist it inside the chroot."""
        if self.is_mock:
            content = "/dev/sda1  /   ext4    defaults    0 1\n/dev/sda2  swap   swap    defaults    0 0\n"
            self.fs_handler.create_file("etc/fstab", content)
            logging.getLogger("chroot").info(
                "[MOCK FS] /etc/fstab simulated successfully, content:\n" + content
            )
            return f"[MOCK FS] /etc/fstab simulated successfully, content:\n{content}"

        # Real mode - create fstab file directly (no command execution needed)
        try:
            fstab_path = self.chroot_path / "etc" / "fstab"
            fstab_dir = fstab_path.parent
            if not fstab_dir.exists():
                fstab_dir.mkdir(parents=True, exist_ok=True)

            content = "/dev/sda1  /   ext4    defaults    0 1\n/dev/sda2  swap   swap    defaults    0 0\n"
            fstab_path.write_text(content, encoding="utf-8")
            self.logger.info("[REAL] /etc/fstab created successfully.")
            return f"[REAL] /etc/fstab created at {fstab_path}"
        except Exception as e:
            raise ChrootManagerError(f"Failed to generate real fstab: {e}")

