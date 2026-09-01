import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.toolchain import ToolchainManager


class TestToolchainIsolatedPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="arch_builder_toolchain_")
        self.workdir = Path(self.tmp.name)
        self.build_root = self.workdir / "build_host" / "root.x86_64"
        self.build_root.mkdir(parents=True)
        self.manager = ToolchainManager(self.workdir, mode="real", force_isolated=True)
        self.manager.build_chroot = self.build_root
        self.manager.use_host = False

    def tearDown(self):
        self.tmp.cleanup()

    @patch("core.toolchain.subprocess.run")
    def test_build_host_paths_are_translated_for_mksquashfs(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        source = self.build_root / "airootfs"
        output = self.build_root / "iso-staging" / "arch" / "x86_64" / "airootfs.sfs"

        self.manager.run_tool(["mksquashfs", str(source), str(output), "-noappend"])

        executed = run.call_args.args[0]
        if executed[0] == "sudo":
            executed = executed[1:]
        self.assertEqual(executed[:3], ["chroot", str(self.build_root), "mksquashfs"])
        self.assertEqual(executed[3:5], ["/airootfs", "/iso-staging/arch/x86_64/airootfs.sfs"])

    @patch("core.toolchain.subprocess.run")
    def test_target_chroot_is_relative_to_build_host(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        target = self.build_root / "airootfs"

        self.manager.run_command(
            ["bash", "-c", "grub-mkimage -o /tmp/boot.img"],
            chroot_path=str(target),
        )

        executed = run.call_args.args[0]
        if executed[0] == "sudo":
            executed = executed[1:]
        self.assertEqual(
            executed[:6],
            ["chroot", str(self.build_root), "chroot", "/airootfs", "bash", "-c"],
        )
        self.assertNotIn(str(target), executed)


if __name__ == "__main__":
    unittest.main()
