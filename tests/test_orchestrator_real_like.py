import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.orchestrator import BuildOrchestrator


def _fake_toolchain_setup(self):
    self.toolchain_dir.mkdir(parents=True, exist_ok=True)
    root = self.toolchain_dir / "root.x86_64"
    (root / "boot").mkdir(parents=True, exist_ok=True)
    (root / "airootfs").mkdir(parents=True, exist_ok=True)
    self.build_chroot = root
    self.use_host = False


def _fake_toolchain_cleanup(self):
    return None


class TestOrchestratorRealLike(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="arch_builder_orchestrator_")
        self.root = Path(self.tmp.name)

        # Minimal config tree for real-like orchestration tests.
        (self.root / "architectures").mkdir(parents=True, exist_ok=True)

        (self.root / "global_build.json").write_text(
            json.dumps(
                {
                    "system": {
                        "workdir_base": str(self.root / "workdir"),
                        "binaries": {
                            "grub-mkrescue": "/usr/bin/grub-mkrescue",
                            "genisoimage": "/usr/bin/genisoimage",
                        },
                    }
                }
            )
        )

        (self.root / "architectures" / "x86_64.json").write_text(
            json.dumps({"platform_specific": {"architecture": "x86_64"}})
        )

    def tearDown(self):
        self.tmp.cleanup()

    @patch("core.orchestrator.ToolchainManager.cleanup", _fake_toolchain_cleanup)
    @patch("core.orchestrator.ToolchainManager.setup", _fake_toolchain_setup)
    @patch("core.orchestrator.ISOBuilder.build", lambda self, output_path, workdir=None: Path(output_path))
    def test_real_mode_routes_chroot_to_toolchain_root(self):
        orchestrator = BuildOrchestrator(
            arch="x86_64",
            config_path=str(self.root / "global_build.json"),
            mode="real",
            clean=True,
            force_isolated_toolchain=True,
        )

        # Mock the toolchain to have iso_rootfs_path after setup
        def mock_setup(self):
            _fake_toolchain_setup(self)
            self.iso_rootfs_path = Path(self.build_chroot) / "airootfs"

        with patch("core.orchestrator.ToolchainManager.setup", mock_setup):
            out = self.root / "out.iso"
            result = orchestrator.run_build(str(out))

        self.assertEqual(Path(result), out)
        self.assertIsNotNone(orchestrator.chroot)
        self.assertIsNotNone(orchestrator.toolchain)
        # In isolated mode, chroot should point to the iso_rootfs inside build_chroot
        self.assertTrue(
            orchestrator.chroot.chroot_path == orchestrator.toolchain.iso_rootfs_path
        )

    @patch("core.orchestrator.ToolchainManager.cleanup", _fake_toolchain_cleanup)
    @patch("core.orchestrator.ToolchainManager.setup", _fake_toolchain_setup)
    @patch("core.orchestrator.ISOBuilder.build", lambda self, output_path, workdir=None: Path(output_path))
    def test_no_clean_preserves_stale_dirs(self):
        stale = self.root / "workdir" / "x86_64" / "airootfs"
        stale.mkdir(parents=True, exist_ok=True)
        marker = stale / "marker.txt"
        marker.write_text("keep")

        orchestrator = BuildOrchestrator(
            arch="x86_64",
            config_path=str(self.root / "global_build.json"),
            mode="real",
            clean=False,
            force_isolated_toolchain=True,
        )

        def mock_setup(self):
            _fake_toolchain_setup(self)
            self.iso_rootfs_path = Path(self.build_chroot) / "airootfs"

        with patch("core.orchestrator.ToolchainManager.setup", mock_setup):
            orchestrator.run_build(str(self.root / "out2.iso"))
        self.assertTrue(marker.exists())

    @patch("core.orchestrator.ToolchainManager.cleanup", _fake_toolchain_cleanup)
    @patch("core.orchestrator.ToolchainManager.setup", _fake_toolchain_setup)
    @patch("core.orchestrator.ISOBuilder.build", lambda self, output_path, workdir=None: Path(output_path))
    def test_clean_removes_stale_dirs(self):
        stale = self.root / "workdir" / "x86_64" / "airootfs"
        stale.mkdir(parents=True, exist_ok=True)
        marker = stale / "marker.txt"
        marker.write_text("remove")

        orchestrator = BuildOrchestrator(
            arch="x86_64",
            config_path=str(self.root / "global_build.json"),
            mode="real",
            clean=True,
            force_isolated_toolchain=True,
        )

        def mock_setup(self):
            _fake_toolchain_setup(self)
            self.iso_rootfs_path = Path(self.build_chroot) / "airootfs"

        with patch("core.orchestrator.ToolchainManager.setup", mock_setup):
            orchestrator.run_build(str(self.root / "out3.iso"))
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()