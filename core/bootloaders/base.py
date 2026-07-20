from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class Bootloader(ABC):
    """
    Abstract base class for all bootloader implementations.
    Defines the interface required by the ISO build process.
    """

    def __init__(self, config: Any):
        self.config = config

    @abstractmethod
    def prepare_files(self, workdir: Path) -> bool:
        """Prepare the files required by the bootloader (for example, grub.cfg or isolinux.cfg)."""

    @abstractmethod
    def generate_boot_image(
        self, workdir: Path, chroot_path: Optional[Path] = None
    ) -> bool:
        """
        Generate the final boot image (for example, via grub-mkrescue).
        Includes optional chroot_path to match child class implementations.
        """

    @abstractmethod
    def validate(self, workdir: Path) -> bool:
        """Validate that bootloader files were generated correctly."""
