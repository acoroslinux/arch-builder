import os
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from core.chroot_manager import ChrootManager, MockFSHandler
from core.iso_engine import ArchEngine, BaseEngine, Config, ISOBuilder

# Import modules for tests, assuming the test directory is at the project root.
from core.toolchain_manager import MockToolchainManager, ToolchainManager

# ----------------------------------------------------------------------
# Mocks and setup for end-to-end integration tests
# ----------------------------------------------------------------------


class MockConfig(Config):
    """Mock Config implementation for tests with fixed input data."""

    def __init__(self):
        super().__init__({})
        # Define a valid simulated configuration state.
        self._data = {
            "metadata": {"label": "TEST-ARCH"},
            "platform_specific": {
                "base_kernel": "vmlinuz-linux",
                "initramfs": "arch-base",
                "default_desktop": "xfce",
            },
            "build_environment": {"workdir": "/mock/isofiles"},
        }

    def get(self, path: str, default: Any = None) -> Any:
        """Mock a generic get method."""
        if path == "system":
            return {
                "workdir_base": "/mnt/build-chroot",  # Fixed chroot path for the test.
                "binaries": {
                    "grub-mkrescue": "/usr/bin/mock-grub",
                    "genisomake": "/usr/local/bin/mock-geniso",
                },
            }
        if path == "packages":
            return ["base", "networking"]  # Packages we want to test in mock mode.
        if path == "workdir_base":
            return "/mnt/build-chroot"
        if path == "system_info":
            return {
                "root_device_id": "/dev/disk/by-uuid/TEST-ARCH",
                "workdir_base": "/mnt/build-chroot",
            }
        return default


# ----------------------------------------------------------------------
# Main integration test
# ----------------------------------------------------------------------


class TestArchBuilderIntegration(unittest.TestCase):
    def setUp(self):
        """Prepare test state before each run by initializing mocks."""
        print("\n" + "=" * 50)
        print("STARTING FULL ARCH-BUILDER INTEGRATION TEST")
        print("=" * 50 + "\n")
        self.mock_toolchain = MockToolchainManager("/tmp/test-build-host")
        # Pass the mock filesystem into the chroot to simulate test interactions.
        self.mock_chroot_manager = ChrootManager(
            workdir="/mnt/build-chroot", chroot_mode=True
        )
        self.mock_config = MockConfig()

    def test_full_e2e_build_cycle_simulation(self):
        """Test the full ISO build lifecycle using mocks to simulate real execution."""
        print(
            "\n--- Testing full cycle: config -> chroot setup -> install -> post-config -> build ---"
        )

        # 1. Initialize the builder and retrieve the engine (tests the registry pattern).
        try:
            builder = ISOBuilder("x86_64", self.mock_config, self.mock_toolchain)
            engine: BaseEngine = builder.engine
        except NotImplementedError as e:
            self.fail(f"Failed to retrieve the engine through the registry pattern: {e}")
            return

        # 2. Run the build (tests all methods sequentially).
        output_file = "/tmp/mock-test-image.iso"
        try:
            builder.build_iso(output_file)
            print(
                "\n✅ E2E TEST SUCCESS: the simulated build workflow finished without critical failures."
            )

        except Exception as e:
            self.fail(
                f"The build cycle failed unexpectedly during simulation: {type(e).__name__}: {str(e)}"
            )


if __name__ == "__main__":
    unittest.main()
