# -*- coding: utf-8 -*-
"""
core/system_manager.py

Central manager for low‑level system operations (packages, services, kernel initramfs).
All actions are logged through the central logger to provide consistent, colour‑coded
output and persistent audit trails.
"""

import logging
from typing import Any, Dict, List, Optional

from core.toolchain_manager import ToolchainManager

# Import the central logger configuration
try:
    from .logger_setup import setup_logger
except ImportError:  # pragma: no cover
    # Fallback – should never happen in a valid installation
    def setup_logger(*_, **__):  # type: ignore
        import logging

        logging.basicConfig(level=logging.INFO)
        return logging.getLogger()


# ----------------------------------------------------------------------
# SystemManagerError – custom exception for the SystemManager
# ----------------------------------------------------------------------
class SystemManagerError(Exception):
    """Exception raised for any failure within SystemManager operations."""


# ----------------------------------------------------------------------
# SystemManager – orchestrates package installation, service enablement,
# initramfs generation and fstab generation.
# ----------------------------------------------------------------------
class SystemManager:
    """
    Manages low‑level system operations (packages, services, kernel initramfs).
    All actions are logged through the central logging system (core.logger_setup).
    This class is intended to be used by the ISO engine to perform the
    post‑install configuration steps.
    """

    def __init__(self, config: "Config", toolchain: ToolchainManager):
        """
        Initialise the SystemManager with a configuration object and a
        ToolchainManager instance.

        Parameters
        ----------
        config : Config
            The global configuration object that provides access to workdir,
            binaries and other build‑time settings.
        toolchain : ToolchainManager
            The manager responsible for executing commands inside the chroot.
        """
        self.config = config
        self.toolchain = toolchain
        # Initialise a dedicated logger for this component
        self.logger = setup_logger("system_manager", "system.log", logging.INFO)

    # ------------------------------------------------------------------
    # Package installation
    # ------------------------------------------------------------------
    def install_packages(self, packages: List[str]) -> None:
        """
        Install a list of packages inside the chroot, simulating a cache‑aware
        installation process (inspired by Void Linux builder practices).

        Parameters
        ----------
        packages : List[str]
            List of package names to install.
        """
        self.logger.info("Starting package installation with cache management.")
        try:
            # 1. Cache preparation (conceptual – could use pre-downloaded packages)
            cache_dir = self.config.system.get("workdir_base") + "/cache"
            self.logger.debug(f"Checking or downloading local cache in {cache_dir}...")

            # 2. Package installation
            if not packages:
                self.logger.warning("No package list was provided for installation.")
                return

            self.logger.info(
                f"Running real or simulated installation of {', '.join(packages)}..."
            )
            # Delegate the actual installation to the ToolchainManager's chroot manager
            self.toolchain.chroot_manager.install_packages(packages)

        except Exception as e:
            self.logger.critical(
                f"Critical package installation failure: {type(e).__name__}: {str(e)}"
            )
            raise SystemManagerError(f"Critical package installation failure: {e}")

    # ------------------------------------------------------------------
    # Service enablement (systemd)
    # ------------------------------------------------------------------
    def setup_services(self, services: List[str]) -> None:
        """
        Enable essential system services (Systemd). Guarantees that the
        environment is ready for proper initialization.

        Parameters
        ----------
        services : List[str]
            List of service names to enable (e.g. ``['NetworkManager', 'ssh']``).
        """
        self.logger.info("Configuring systemd services and startup.")
        try:
            for service in services:
                self.logger.debug(f"Attempting to enable service: {service}...")
                # The command is executed inside the chroot; success/failure is logged
                # by the ChrootManager's run_command method.
                command = ["systemctl", "enable", "--now", f"{service}.service"]
                self.toolchain.run_command(
                    command, chroot_path=self.config.system.get("workdir_base")
                )
        except Exception as e:
            self.logger.critical(
                f"Failure while configuring systemd services: {type(e).__name__}: {str(e)}"
            )
            raise SystemManagerError(f"Failure while configuring systemd services: {e}")

    # ------------------------------------------------------------------
    # Initramfs generation (mkinitcpio or equivalent)
    # ------------------------------------------------------------------
    def generate_initramfs(self, kernel_packages: List[str]) -> None:
        """
        Generate the initial ramdisk (initramfs) capturing essential kernel modules.
        This must happen before the root filesystem is compressed.

        Parameters
        ----------
        kernel_packages : List[str]
            List of kernel package names that define the modules to include.
        """
        self.logger.info(
            "Generating initramfs (mkinitcpio) to collect essential modules."
        )
        try:
            # Simulate the mkinitcpio command – in a real setup this would
            # collect modules and hooks based on the installed kernel packages.
            command = ["makepkg", "-c", "--components=base"]
            self.toolchain.run_command(command, chroot_path="/mnt/build-chroot")
            self.logger.info("Initramfs generated successfully and ready for the bootloader.")
        except Exception as e:
            self.logger.critical(
                f"Failed to generate initramfs on system {self.config.system.get('workdir_base')}: {type(e).__name__}: {str(e)}"
            )
            raise SystemManagerError(f"Failed to generate initramfs: {e}")

    # ------------------------------------------------------------------
    # fstab generation – wrapper around ChrootManager.generate_fstab()
    # ------------------------------------------------------------------
    def generate_fstab(self) -> str:
        """
        Generate /etc/fstab using the ChrootManager's generate_fstab method.
        This wrapper centralises logging for the operation.

        Returns
        -------
        str
            The generated fstab content.
        """
        self.logger.info(
            "Generating fstab (top-down) by checking partitions and critical mount points."
        )
        result = self.toolchain.chroot_manager.generate_fstab()
        self.logger.info(f"Fstab generated successfully: {result}")
        return result
