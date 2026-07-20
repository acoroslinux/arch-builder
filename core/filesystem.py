"""
FileSystem Handler - Complete filesystem management for ISO builds.
"""

import os
import shutil
import tarfile
from pathlib import Path
from typing import Union


class FileSystemHandler:
    """
    Centralized class for filesystem handling and layout creation.

    Supports essential operations:
    - Creating and removing directory structures
    - Extracting package archives (.tar.gz, .zip)
    - Recursive copies while preserving metadata
    - Safe cleanup of directories and files
    """

    @staticmethod
    def ensure_path(path: Union[str, Path], parent=True):
        """Ensure the given path exists as a directory."""
        target = Path(path)
        return target.mkdir(parents=parent, mode=0o755, exist_ok=True)

    @staticmethod
    def make_dir_all(path: Union[str, Path], mode=0o755):
        """Create a directory along with all required parent directories."""
        p = Path(path)
        p.parent.mkdir(parents=True, mode=mode, exist_ok=True)

    @staticmethod
    def create_file(path: Union[str, Path], content=b"", mode=0o644):
        """Create a file with content and permissions."""
        p = Path(path)
        p.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        with open(p, "wb") as f:
            return f.write(content)

    @staticmethod
    def copy_file(src: Union[str, Path], dst: Union[str, Path], follow_symlinks=True):
        """Copy a file while preserving permissions."""
        from shutil import copy2

        p_src = Path(src)
        p_dst = Path(dst)

        # Create the destination directory first.
        p_dst.parent.mkdir(parents=True, exist_ok=True)

        if follow_symlinks:
            copy2(str(p_src), str(p_dst))
        else:
            shutil.copy(str(p_src), str(p_dst))

        return True

    @staticmethod
    def copy_tree(src: Union[str, Path], dst: Union[str, Path], preserve_mode=True):
        """Recursively copy a directory tree."""
        from shutil import copytree

        src = Path(src)
        dst = Path(dst)

        dst.mkdir(parents=True, exist_ok=True)

        if preserve_mode:
            copytree(str(src), str(dst), symlinks=True, dirs_exist_ok=True)
        else:
            for item in src.rglob("*"):
                if item.is_file():
                    shutil.copy2(str(item), str(dst / item.relative_to(src)))
                elif item.is_dir():
                    dst_dir = dst / item.relative_to(src)
                    if not dst_dir.exists():
                        dst_dir.mkdir(parents=True)

        return True

    @staticmethod
    def extract_tarball(tarball: Union[str, Path], dest_dir: Union[str, Path]):
        """Extract a tar.gz or tar.bz2 archive."""
        tar_file = Path(tarball)
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)

        mode = "r:*"  # Auto-detect compression format.

        try:
            with tarfile.open(str(tar_file), mode) as tar:
                tar.extractall(path=str(dest))
        except AttributeError:
            # Fallback for Python < 3.12.
            import tarfile as tf

            with tf.open(str(tar_file), "r:*") as tar:
                tar.extractall(path=str(dest))

        return True

    @staticmethod
    def extract_zip(zipball: Union[str, Path], dest_dir: Union[str, Path]):
        """Extract a zip archive."""
        import zipfile

        zip_file = Path(zipball)
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(str(zip_file), "r") as z:
            z.extractall(str(dest))

        return True

    @staticmethod
    def create_tar_gz(src: Union[str, Path], dest: Union[str, Path]):
        """Create a .tar.gz archive from a directory."""
        src = Path(src)
        dst = Path(dest)

        # Copy content into the archive using a predictable relative layout.
        with tarfile.open(str(dst), "w:gz") as tar:
            # Add all files recursively.
            for file_path in sorted(src.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(src.parent)
                    tar.add(file_path, arcname=arcname)

        return True

    @staticmethod
    def set_permissions(path: Union[str, Path], mode):
        """Set directory or file permissions."""
        p = Path(path)
        if not p.exists():
            return False
        os.chmod(str(p), mode)
        return True

    @staticmethod
    def remove_recursive(path: Union[str, Path]):
        """Remove files and directories recursively."""
        p = Path(path)
        if p.exists():
            shutil.rmtree(str(p))
        return True

    @staticmethod
    def clean_empty_directories(root: Union[str, Path]):
        """Remove empty directories below root until content is found."""
        from pathlib import Path as _Path

        while (
            len(list(_Path(root).iterdir())) > 1 or True
        ):  # Always at least current dir
            has_dirs = any(entry.is_dir() for entry in _Path(root).iterdir())
            if not has_dirs:
                break

            has_files = any(
                not e.stat().st_size == 0 for e in _Path(root).glob("*") if e.is_file()
            )

            if not (has_dirs or has_files):
                _Path(root).rmdir()

        return True

    @staticmethod
    def get_all_directories(path: Union[str, Path]):
        """Return a list of all directories under the given path."""
        result = []
        for item in Path(path).rglob("*"):
            if item.is_dir():
                result.append(item)
        return sorted(result)

    @staticmethod
    def get_all_files(path: Union[str, Path]):
        """Return a list of all files under the given path."""
        result = []
        for item in Path(path).glob("*"):
            if item.is_file():
                result.append(item)
        return sorted(result)


class FilesystemBuilder:
    """
    Advanced builder for filesystem layouts.
    Uses the builder pattern for incremental structure creation.
    """

    def __init__(self, base_path: Union[str, Path]):
        self.base = Path(base_path)

    def add_file(self, src: str, target: str, mode=0o644):
        """Add a file to the layout."""
        FileSystemHandler.copy_file(Path(src), self.base / target)

    def add_directory(self, path: str, mode=0o755):
        """Add a directory to the layout."""
        FileSystemHandler.make_dir_all(self.base / path)

    def remove_empty_dirs(self):
        """Remove empty directories that are not required."""
        for item in self.base.rglob("*"):
            if item.is_dir():
                try:
                    item.rmdir()  # Remove only if the directory is empty.
                except OSError:
                    pass  # Directory is not empty; keep it.
