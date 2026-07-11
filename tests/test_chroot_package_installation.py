import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from core.chroot_manager import ChrootManager, ChrootManagerError


class TestChrootPackageInstallation(unittest.TestCase):
    def test_mock_mode_installation(self):
        # Initialize ChrootManager in mock mode (which is default when mode != "real")
        manager = ChrootManager(workdir="/tmp/mock-chroot", mode="mock")
        
        # Mock fs_handler to check if keys file is simulated
        manager.fs_handler = MagicMock()
        
        plan = {
            "official": ["base", "linux"],
            "aur": ["yay-bin"],
            "local_paths": ["/tmp/pkg-1.pkg.tar.zst"]
        }
        
        manager.install_packages(plan)
        
        # Verify simulated key creation
        manager.fs_handler.create_file.assert_called_once_with("etc/apk/keys", "MOCK-KEY-DATA")

    @patch("core.chroot_manager.shutil.copy2")
    @patch("core.chroot_manager.os.path.isdir")
    @patch("core.chroot_manager.Path.exists")
    @patch("core.chroot_manager.Path.is_file")
    def test_real_mode_installation_flow(self, mock_is_file, mock_exists, mock_isdir, mock_copy):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_isdir.return_value = True
        
        # Initialize ChrootManager in real mode with isolated toolchain simulation
        mock_toolchain = MagicMock()
        mock_toolchain.use_host = False
        mock_toolchain.build_chroot = "/tmp/real-chroot"
        mock_toolchain.iso_rootfs_path = None
        manager = ChrootManager(workdir="/tmp/real-chroot", mode="real", toolchain=mock_toolchain)
        
        # Mock run_command and mounting to verify internal commands called
        manager.run_command = MagicMock(return_value="ok")
        manager._mount_essential_filesystems = MagicMock()
        manager._unmount_essential_filesystems = MagicMock()
        
        plan = {
            "official": ["base", "linux"],
            "aur": ["yay-bin"],
            "local_paths": ["/tmp/pkg-1.pkg.tar.zst"]
        }
        
        manager.install_packages(plan)
        
        # 1. Verify official packages installation via pacman -S
        manager.run_command.assert_any_call(
            ["pacman", "-S", "--needed", "--noconfirm", "--disable-download-timeout", "base", "linux"],
            chroot_path="/tmp/real-chroot"
        )
        
        # 2. Verify local packages copy and installation via pacman -U
        mock_copy.assert_called_once()
        manager.run_command.assert_any_call(
            ["pacman", "-U", "--noconfirm", "/tmp/custom-packages/pkg-1.pkg.tar.zst"],
            chroot_path="/tmp/real-chroot"
        )
        
        # 3. Verify AUR packages prerequisites, useradd, git clone, and makepkg commands
        manager.run_command.assert_any_call(
            ["pacman", "-S", "--needed", "--noconfirm", "git", "base-devel"],
            chroot_path="/tmp/real-chroot"
        )
        manager.run_command.assert_any_call(
            ["bash", "-lc", "id -u aurbuilder >/dev/null 2>&1 || useradd -m aurbuilder"],
            chroot_path="/tmp/real-chroot"
        )
        manager.run_command.assert_any_call(
            ["bash", "-lc", "mkdir -p /etc/sudoers.d && echo 'aurbuilder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/aurbuilder"],
            chroot_path="/tmp/real-chroot"
        )
        manager.run_command.assert_any_call(
            ["runuser", "-u", "aurbuilder", "--", "bash", "-lc", 
             "set -e; cd /tmp; rm -rf yay-bin; git clone https://aur.archlinux.org/yay-bin.git; cd yay-bin; makepkg -s --noconfirm --needed"],
            chroot_path="/tmp/real-chroot"
        )
        manager.run_command.assert_any_call(
            ["bash", "-lc", "set -e; cd /tmp/yay-bin; yes | pacman -U --needed *.pkg.tar.zst"],
            chroot_path="/tmp/real-chroot"
        )

    @patch("core.chroot_manager.shutil.which", return_value=None)
    def test_real_mode_host_fallback_requires_pacman(self, mock_which):
        mock_toolchain = MagicMock()
        mock_toolchain.use_host = True
        mock_toolchain.build_chroot = "/tmp/real-chroot"
        manager = ChrootManager(workdir="/tmp/real-chroot", mode="real", toolchain=mock_toolchain)

        with self.assertRaises(ChrootManagerError) as cm:
            manager._install_official_packages_real(["base"], attempts=1)

        self.assertIn("Host pacman is unavailable", str(cm.exception))

    @patch("core.chroot_manager.shutil.which", return_value=None)
    def test_real_mode_local_package_install_requires_pacman(self, mock_which):
        mock_toolchain = MagicMock()
        mock_toolchain.use_host = True
        mock_toolchain.build_chroot = "/tmp/real-chroot"
        manager = ChrootManager(workdir="/tmp/real-chroot", mode="real", toolchain=mock_toolchain)

        with self.assertRaises(ChrootManagerError) as cm:
            manager._install_local_packages_real(["/tmp/pkg-1.pkg.tar.zst"])

        self.assertIn("Host pacman is unavailable", str(cm.exception))

    @patch("core.chroot_manager.shutil.which", return_value=None)
    def test_real_mode_aur_package_install_requires_pacman(self, mock_which):
        mock_toolchain = MagicMock()
        mock_toolchain.use_host = True
        mock_toolchain.build_chroot = "/tmp/real-chroot"
        manager = ChrootManager(workdir="/tmp/real-chroot", mode="real", toolchain=mock_toolchain)

        with self.assertRaises(ChrootManagerError) as cm:
            manager._install_aur_packages_real(["yay-bin"])

        self.assertIn("Host pacman is unavailable", str(cm.exception))

    def test_aur_package_name_validation(self):
        mock_toolchain = MagicMock()
        mock_toolchain.use_host = False
        mock_toolchain.build_chroot = "/tmp/real-chroot"
        mock_toolchain.iso_rootfs_path = None
        manager = ChrootManager(workdir="/tmp/real-chroot", mode="real", toolchain=mock_toolchain)
        manager.run_command = MagicMock(return_value="ok")
        manager._mount_essential_filesystems = MagicMock()
        manager._unmount_essential_filesystems = MagicMock()
        
        # Plan containing an invalid AUR package name (with semicolon to try command injection)
        plan = {
            "official": [],
            "aur": ["yay-bin; rm -rf /"],
            "local_paths": []
        }
        
        # Should raise RuntimeError due to invalid package name causing ChrootManagerError
        with self.assertRaises(RuntimeError):
            manager.install_packages(plan)


if __name__ == "__main__":
    unittest.main()
