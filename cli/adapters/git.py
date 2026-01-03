"""
Git repository adapter for file discovery operations.

This module provides a high-level interface for interacting with Git repositories
to discover and enumerate files. It abstracts subprocess calls to git commands
and provides streaming generators for memory-efficient file path enumeration.
"""

from pathlib import Path
import subprocess
from typing import Generator, Optional


class GitClient:
    """
    Client for interacting with Git repositories.

    This class provides methods to query Git repositories for file information,
    check repository status, and stream file paths efficiently. It encapsulates
    all Git subprocess operations and provides a clean interface for the discovery
    pipeline.

    Attributes:
        root: The root path of the Git repository this client operates on.
    """

    def __init__(self, root: Path):
        """
        Initialize a GitClient for the specified repository root.

        Args:
            root: The root directory path of the Git repository.
        """
        self.root = root

    def is_repo(self) -> bool:
        """
        Check if the root path is a valid Git repository.

        This method verifies that the root directory is inside a Git working tree
        by executing `git rev-parse --is-inside-work-tree`. This is a lightweight
        check that doesn't require reading the entire repository structure.

        Returns:
            bool: True if the root is a valid Git repository, False otherwise.
        """
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.root,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def count_files(self, scopes: list[str]) -> int:
        """
        Efficiently counts the number of lines (files) in a Git command output.

        This function executes the provided command and streams the output to count newlines
        without loading the entire output into memory. This is used to calculate totals for
        progress bars before processing begins.

        Args:
            scopes (list[str]): The paths for git to look into to count files

        Returns:
            int: The total number of lines/files returned by the command.
        """

        # Construct the command: git ls-files ... -- path1 path2
        # The "--" separator tells git "everything after this is a path"
        cmd = self._build_ls_files_cmd(scopes)

        count = 0
        # Use Popen to open a pipe, not a buffer
        with self._create_subprocess(cmd) as process:

            # Iterate over the stream directly
            if process.stdout:
                for _ in process.stdout:
                    count += 1

        return count

    def stream_file_paths(
        self, scopes: Optional[list[str]] = None
    ) -> Generator[Path, None, None]:
        """
        Lazily yield all relevant file paths from the Git index and working tree
        in ascending alphabetical order.

        This method executes `git ls-files` to retrieve a list of files that are either
        cached (tracked) or untracked but not ignored (respecting `.gitignore`).
        It uses a subprocess pipe to stream results line-by-line, ensuring memory efficiency
        for large repositories.

        Args:
            scopes: Optional list of relative paths to restrict the search to specific
                directories. If provided, only files within these scopes are returned.
                If None, all files in the repository are returned.

        Yields:
            Path: A relative path object (relative to repository root) for each file
                found in the repository.
        """
        cmd = self._build_ls_files_cmd(scopes)

        with self._create_subprocess(cmd) as process:
            if process.stdout:
                for p in process.stdout:
                    yield Path(p.strip())

            process.wait()

    def _build_ls_files_cmd(self, scopes: Optional[list[str]]) -> list[str]:
        cmd = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
        if scopes:
            cmd += ["--"] + scopes

        return cmd

    def _create_subprocess(self, cmd: list[str]) -> subprocess.Popen[str]:
        return subprocess.Popen(
            cmd,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
