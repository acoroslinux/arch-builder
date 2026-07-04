import shutil
import tempfile
import unittest
from pathlib import Path

from core.chroot_setup import ChrootBuilder
from core.path_utils import project_root


class TestChrootCustomFileCopy(unittest.TestCase):
    def setUp(self):
        self._project_tmp = tempfile.TemporaryDirectory(
            prefix="arch_builder_assets_", dir=project_root()
        )
        self._build_tmp = tempfile.TemporaryDirectory(prefix="arch_builder_build_")

        self.assets_root = Path(self._project_tmp.name)
        self.base_path = Path(self._build_tmp.name)
        self.builder = ChrootBuilder(self.base_path)

    def tearDown(self):
        self._project_tmp.cleanup()
        self._build_tmp.cleanup()

    def _project_relative(self, path: Path) -> str:
        return str(path.relative_to(project_root()))

    def test_copy_custom_files_supports_file_directory_and_auto(self):
        # Explicit file source
        single_src = self.assets_root / "single.conf"
        single_src.write_text("single-value\n")

        # Explicit directory source
        tree_src = self.assets_root / "tree"
        (tree_src / "sub").mkdir(parents=True, exist_ok=True)
        (tree_src / "sub" / "payload.txt").write_text("payload\n")

        # Auto file source
        auto_file_src = self.assets_root / "auto.txt"
        auto_file_src.write_text("auto-file\n")

        # Auto directory source
        auto_dir_src = self.assets_root / "auto-dir"
        auto_dir_src.mkdir(parents=True, exist_ok=True)
        (auto_dir_src / "nested.txt").write_text("auto-dir\n")

        # Prepare destination directory with existing content to validate merge behavior.
        merged_dest = self.builder.chroot_dir / "usr/share/merge-target"
        merged_dest.mkdir(parents=True, exist_ok=True)
        (merged_dest / "preexisting.txt").write_text("keep-me\n")

        rules = [
            {
                "src": self._project_relative(single_src),
                "dest": "/etc/single.conf",
                "type": "file",
            },
            {
                "src": self._project_relative(tree_src),
                "dest": "/usr/share/merge-target",
                "type": "directory",
            },
            {
                "src": self._project_relative(auto_file_src),
                "dest": "/opt/auto-file.txt",
                "type": "auto",
            },
            {
                "src": self._project_relative(auto_dir_src),
                "dest": "/opt/auto-dir",
                "type": "auto",
            },
        ]

        self.builder.copy_custom_files(rules)

        self.assertEqual(
            (self.builder.chroot_dir / "etc/single.conf").read_text(),
            "single-value\n",
        )
        self.assertEqual(
            (self.builder.chroot_dir / "usr/share/merge-target/sub/payload.txt").read_text(),
            "payload\n",
        )
        self.assertEqual(
            (self.builder.chroot_dir / "usr/share/merge-target/preexisting.txt").read_text(),
            "keep-me\n",
        )
        self.assertEqual(
            (self.builder.chroot_dir / "opt/auto-file.txt").read_text(),
            "auto-file\n",
        )
        self.assertEqual(
            (self.builder.chroot_dir / "opt/auto-dir/nested.txt").read_text(),
            "auto-dir\n",
        )


if __name__ == "__main__":
    unittest.main()