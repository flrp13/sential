"""
File discovery and inventory generation module.

This module implements the "Language Sieve" pipeline that scans Git repositories,
identifies modules based on manifest files, and classifies files into language
files (source code) and context files (documentation, configs). It generates
temporary inventory files that are used by downstream processing stages.
"""

from enum import Enum
import tempfile
from pathlib import Path
from typing import IO, Generator, Optional
from adapters.git import GitClient
from constants import LANGUAGES_HEURISTICS, UNIVERSAL_CONTEXT_FILES
from core.exceptions import (
    EmptyInventoryError,
    TempFileCreationError,
    TempFileWriteError,
)
from core.models import InventoryResult, InventoryStats
from models import SupportedLanguage
from ui.progress import ProgressState, create_progress, create_task, update_progress


class FileCategory(Enum):
    """
    Enumeration of file classification categories.

    Files are classified into one of these categories during the discovery phase
    to determine how they should be processed in subsequent pipeline stages.

    Attributes:
        LANGUAGE: Source code files matching the target language extensions.
        CONTEXT: High-value context files (docs, manifests, configs).
        IGNORE: Files that don't match any category and are excluded.
    """

    LANGUAGE = "lang"
    CONTEXT = "context"
    IGNORE = "ignore"


def get_focused_inventory(
    base_path: Path, language: SupportedLanguage
) -> Generator[Path, None, None]:
    """
    Scans the repository to identify potential module roots based on language-specific heuristics.

    This generator consumes the raw Git file stream and applies a "Language Sieve."
    It looks for specific manifest files (e.g., `package.json` for TypeScript, `Cargo.toml`
    for Rust) defined in `LANGUAGES_HEURISTICS` to identify directories that represent
    distinct modules or sub-projects within the repository.

    Args:
        base_path (Path): The absolute root path of the repository.
        language (SupportedLanguages): The enum representing the selected programming language,
            used to determine which manifest files to look for.

    Yields:
        Path: The relative path to the parent directory of a found manifest file,
        effectively identifying a module root (e.g., "src/backend" or ".").
    """

    git_client = GitClient(base_path)
    raw_stream = git_client.stream_file_paths()

    manifests = LANGUAGES_HEURISTICS[language]["manifests"]

    for file_path in raw_stream:
        rel_path = file_path.parent

        if file_path.name.lower() in manifests:
            yield rel_path


class FileInventoryWriter:
    """
    Context manager that scans a Git repository and generates inventory files.

    Classifies files into language files (source code) and context files (docs, configs)
    based on language-specific heuristics. Writes file paths to temporary inventory files
    that are consumed by downstream processing stages.

    Must be used as a context manager. The context manager handles cleanup of
    temporary files after processing completes.
    """

    def __init__(self, root_path: Path, scopes: list[str], language: SupportedLanguage):
        """
        Initialize the file inventory writer.

        Args:
            root_path: Root directory of the Git repository to scan.
            scopes: List of relative paths to restrict scanning to specific directories.
            language: Target programming language for file classification.
        """
        self.root_path = root_path
        self.scopes = scopes
        self.language = language
        self.git_client = GitClient(self.root_path)
        self.total_files = self.git_client.count_files(self.scopes)
        self.file_stream = self.git_client.stream_file_paths(self.scopes)
        # Get the allowed extensions (e.g., {'.js', '.ts'})
        self.allowed_extensions = LANGUAGES_HEURISTICS[self.language]["extensions"]

        # Create the fast lookup set for the Reader (O(1) checks)
        self.allowed_context_files: frozenset[str] = (
            frozenset(UNIVERSAL_CONTEXT_FILES)
            | LANGUAGES_HEURISTICS[self.language]["manifests"]
        )
        self.lang_file_count = 0
        self.ctx_file_count = 0
        self.processed_files_chunk = 0

        # File handles and paths - set in __enter__, closed in process(), cleaned up in __exit__
        self.lang_file: Optional[IO[str]] = None
        self.context_file: Optional[IO[str]] = None
        self.lang_file_path: Optional[Path] = None
        self.context_file_path: Optional[Path] = None

    @property
    def _lang_file(self) -> IO[str]:
        """Type-safe access to lang_file, ensuring context manager was entered."""
        if self.lang_file is None:
            raise RuntimeError(
                "FileInventoryWriter.lang_file is not initialized. "
                "Did you forget to use 'with FileInventoryWriter(...) as writer'?"
            )
        return self.lang_file

    @property
    def _context_file(self) -> IO[str]:
        """Type-safe access to context_file, ensuring context manager was entered."""
        if self.context_file is None:
            raise RuntimeError(
                "FileInventoryWriter.context_file is not initialized. "
                "Did you forget to use 'with FileInventoryWriter(...) as writer'?"
            )
        return self.context_file

    @property
    def _advance(self) -> int:
        """We use this to define the advance amount for progress bar"""
        if self.total_files <= 100:
            return 1
        return 5 * (len(str(self.total_files)) - 1)

    def __enter__(self):
        """
        Create temporary inventory files for writing file paths.

        Returns:
            self: Returns the instance for use in 'with' statements.
        """
        # Create temp files - we'll manage their lifecycle explicitly
        try:
            self.lang_file = tempfile.NamedTemporaryFile(
                mode="w", delete=False, encoding="utf-8"
            )
            self.context_file = tempfile.NamedTemporaryFile(
                mode="w", delete=False, encoding="utf-8"
            )
            self.lang_file_path = Path(self.lang_file.name)
            self.context_file_path = Path(self.context_file.name)
        except OSError as e:
            raise TempFileCreationError from e
        return self

    def __exit__(self, *args):
        """
        Clean up temporary inventory files.

        Files are already closed by process(), so this only removes the temp files
        from disk. Called automatically when exiting the 'with' block.
        """
        # Context manager only handles cleanup - files are already closed by process()
        if self.lang_file_path and self.lang_file_path.exists():
            self.lang_file_path.unlink(missing_ok=True)
        if self.context_file_path and self.context_file_path.exists():
            self.context_file_path.unlink(missing_ok=True)

    def process(self) -> InventoryResult:
        """
        Scan repository files and generate inventory files.

        Iterates through all files in the repository, classifies them by category,
        and writes file paths to temporary inventory files. Closes file handles
        before returning so the files can be read by downstream processes.

        Returns:
            InventoryResult containing paths to inventory files and file counts.

        Raises:
            EmptyInventoryError: If no files are found in the repository matching the
                specified language and scopes.
            RuntimeError: If not used as a context manager (files not initialized).
        """
        # Handle empty repository or empty scopes - raise exception to stop processing
        if self.total_files == 0:
            raise EmptyInventoryError(
                "No files found in the repository matching the specified language and scopes"
            )

        try:
            with create_progress() as progress:
                task = create_task(
                    progress,
                    "Scanning files and applying language filter...",
                    total=self.total_files,
                )
                for file_path in self.file_stream:

                    # Check file category to know which file to write it to
                    category = classify_file(
                        file_path, self.allowed_extensions, self.allowed_context_files
                    )
                    self._write_to_file_by_category(file_path, category)

                    self.processed_files_chunk += 1

                    if self.processed_files_chunk == self._advance:
                        # Advance the raw counter
                        update_progress(progress, task, advance=self._advance)
                        update_progress(
                            progress,
                            task,
                            ProgressState.IN_PROGRESS,
                            description=f"Kept {self.lang_file_count + self.ctx_file_count} {self.language} files...",
                        )
                        self.processed_files_chunk = 0

                # Final update - progress bar completes when 'with' block exits
                update_progress(
                    progress,
                    task,
                    ProgressState.COMPLETE,
                    description=f"✅ Found {self.lang_file_count + self.ctx_file_count} valid files",
                    completed=self.total_files,
                )
        finally:
            # Close file handles explicitly - closing flushes automatically
            # Files remain on disk (delete=False) for generate_tags_jsonl() to read
            # Access attributes directly (not properties) to avoid RuntimeError in cleanup
            # Use try/except to avoid masking original exceptions if close() fails
            if self.lang_file is not None:
                try:
                    self.lang_file.close()
                except OSError:
                    pass
            if self.context_file is not None:
                try:
                    self.context_file.close()
                except OSError:
                    pass

        # Type narrowing: paths are set in __enter__, so they're guaranteed non-None here
        if self.lang_file_path is None or self.context_file_path is None:
            raise RuntimeError(
                "Inventory paths were not initialized. This usually means "
                "the process() method was called outside of a valid context."
            )

        return InventoryResult(
            self.lang_file_path,
            self.context_file_path,
            InventoryStats(
                self.lang_file_count,
                self.ctx_file_count,
            ),
        )

    def _write_to_file_by_category(
        self, file_path: Path, category: FileCategory
    ) -> None:
        """
        Write file path to the appropriate inventory file based on category.

        Args:
            file_path: Relative path to the file to write.
            category: Classification category determining which inventory file to use.
        """
        try:
            match category:
                case FileCategory.LANGUAGE:
                    self.lang_file_count += 1
                    self._lang_file.write(f"{file_path}\n")
                case FileCategory.CONTEXT:
                    self.ctx_file_count += 1
                    self._context_file.write(f"{file_path}\n")
                case _:
                    pass
        except IOError as e:
            raise TempFileWriteError from e


def classify_file(
    path: Path,
    allowed_extensions: frozenset[str],
    allowed_context_files: frozenset[str],
) -> FileCategory:
    """
    Classify a file path into a category based on extension and name.

    Classification priority:
    1. LANGUAGE: If file extension matches allowed extensions for the target language.
    2. CONTEXT: If file name matches known context files, starts with "readme", or is a .md file.
    3. IGNORE: All other files.

    Args:
        path: File path to classify.
        allowed_extensions: Set of file extensions that match the target language.
        allowed_context_files: Set of file names that are considered context files.

    Returns:
        FileCategory enum value indicating how the file should be processed.
    """
    file_name = path.name.lower()
    suffix = path.suffix.lower()

    # Check Language
    if suffix in allowed_extensions:
        return FileCategory.LANGUAGE

    # Check Context
    if (
        file_name in allowed_context_files
        or file_name.startswith("readme")
        or suffix == ".md"
    ):
        return FileCategory.CONTEXT

    return FileCategory.IGNORE
