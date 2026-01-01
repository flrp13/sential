"""
Sential CLI Entry Point.

This module implements the main command-line interface for Sential, a tool designed
to generate high-signal context bridges from local Git repositories. It orchestrates
the scanning pipeline by filtering files based on language-specific heuristics,
scoping the scan to specific modules (monorepo support), and aggregating both
raw file content (for context) and code symbols (via Universal Ctags).

The pipeline operates in four distinct stages:

1.  **Validation & Selection**: Verifies the target path is a valid Git repository
    and handles interactive user selection for the target programming language and
    application scopes (modules).
2.  **Inventory Generation**: Streams the Git index to separate files into 'Language'
    (source code) and 'Context' (manifests/docs) buckets using the "Language Sieve"
    approach defined in `constants.py`.
3.  **Content Extraction**: Reads high-priority context files in full (with intelligent
    truncation) to establish the repository's configuration and documentation baseline.
4.  **Symbol Extraction**: Pipes source files through Universal Ctags to extract structural
    code symbols (classes, functions, definitions) without including full implementation
    details, optimizing token usage for downstream consumption.

Usage:
    Run directly as a script or via the installed entry point.

    $ python main.py --path /path/to/repo --language Python

Dependencies:
    - Typer: CLI argument parsing and app structure.
    - Rich: Terminal UI, colors, and progress visualization.
    - Inquirer: Interactive terminal user prompts.
    - Universal Ctags: External engine used for symbol extraction.
"""

import io
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Generator
import typer
from rich import print as pr
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
import inquirer  # type: ignore
from inquirer.themes import GreenPassion  # type: ignore
from ctags import get_ctags_path

from constants import (
    CTAGS_KINDS,
    UNIVERSAL_CONTEXT_FILES,
    SupportedLanguages,
    LANGUAGES_HEURISTICS,
)
from utils import debug, is_binary_file

app = typer.Typer()


@app.command()
def main(
    path: Annotated[
        Path,
        typer.Option(
            exists=True,  # Typer throws error if path doesn't exist
            file_okay=False,  # Typer throws error if it's a file, not a dir
            dir_okay=True,  # Must be a directory
            resolve_path=True,  # Automatically converts to absolute path
            help="Root path from which Sential will start identifying modules",
        ),
    ] = Path("."),
    language: Annotated[
        str,
        typer.Option(
            help=f"Available languages: {', '.join([l.value for l in SupportedLanguages])}"
        ),
    ] = "",
):
    """
    The main entry point for the Sential CLI application.

    This function orchestrates the entire scanning process. It validates that the
    provided path is a valid Git repository, determines the programming language
    (either via arguments or user prompt), allows the user to select specific
    application scopes (modules), and generates a final JSONL payload containing
    context files and code symbols (ctags).

    Args:
        path (Path): The root directory of the codebase to scan. Must be an existing
            directory and a valid Git repository. Defaults to the current working directory.
        language (str): The target programming language for the scan. If not provided
            via CLI arguments, the user will be prompted to select one interactively.

    Raises:
        typer.Exit: If the path is not a git repository or if an unsupported language is selected.
    """

    # Validate path is git repository
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        pr(f"[red]Error:[/red] Not a git repository: [green]'{path}'[/green]")
        raise typer.Exit() from e

    # Validate language selection
    if not language:
        # If language not passed as arg, show options
        language = make_language_selection()
    # Validate user-entered language is supported
    elif language.lower() not in (l.value.lower() for l in SupportedLanguages):
        pr(
            f"[red]Error:[/red] Selected language not supported ([green]'{language}'[/green]),\n run [italic]sential --help[/italic] to see a list of supported languages."
        )
        raise typer.Exit()

    pr(f"\n[green]Language selected: {language}...[/green]\n")
    pr(f"[green]Scanning: {path}...[/green]\n")

    scopes = select_scope(path, SupportedLanguages(language))
    lang_inventory_path, context_inventory_path, lang_file_count, ctx_file_count = (
        get_final_inventory_file(path, scopes, SupportedLanguages(language))
    )
    tags_map = generate_tags_jsonl(
        path,
        lang_inventory_path,
        context_inventory_path,
        lang_file_count,
        ctx_file_count,
        SupportedLanguages(language),
    )
    print(tags_map)


def get_focused_inventory(
    base_path: Path, language: SupportedLanguages
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

    # Get the stream (Lazy)
    raw_stream = stream_git_inventory(base_path)

    manifests = LANGUAGES_HEURISTICS[language]["manifests"]

    for file_path in raw_stream:
        path_obj = Path(file_path)
        file_name = path_obj.name
        rel_path = path_obj.parent

        if file_name.lower() in manifests:
            yield rel_path


def stream_git_inventory(base_path: Path) -> Generator[Path, None, None]:
    """
    Lazily yields all relevant file paths from the Git index and working tree.

    This function executes `git ls-files` to retrieve a list of files that are either
    cached (tracked) or untracked but not ignored (respecting `.gitignore`).
    It uses a subprocess pipe to stream results line-by-line, ensuring memory efficiency
    for large repositories.

    Args:
        base_path (Path): The absolute root path of the repository where the git command runs.

    Yields:
        Path: A relative path object for each file found in the repository.
    """

    with subprocess.Popen(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=base_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    ) as process:
        if process.stdout:
            for p in process.stdout:
                yield Path(p.strip())

        process.wait()


def select_scope(path: Path, language: SupportedLanguages) -> list[str]:
    """
    Prompts the user to select which modules (scopes) to include in the scan.

    This function first identifies all potential modules using `get_focused_inventory`.
    If multiple modules are found, it presents an interactive checklist (using `inquirer`)
    allowing the user to select specific modules or "Select All".

    Args:
        path (Path): The absolute root path of the repository.
        language (SupportedLanguages): The selected programming language, used to locate modules.

    Returns:
        list[str]: A list of relative path strings representing the selected module roots.
        Returns the original candidate list immediately if "Select All" is chosen or if
        only one module is found.

    Raises:
        typer.Exit: If no modules matching the language heuristics are found in the path.
    """

    candidates = sorted(
        set(str(p) for p in get_focused_inventory(path, SupportedLanguages(language)))
    )

    if not candidates:
        pr(
            f"[bold red]Couldn't find any[/bold red] [italic green]{language.value}[/italic green] [bold red]modules in path:[/bold red] [italic green]{path}[/italic green]"
        )
        raise typer.Exit()

    if len(candidates) == 1:
        return [candidates[0]]

    pr(
        "[bold green]Sential found multiple modules. Which ones should we focus on?[/bold green]\n"
    )

    # This will look like:
    # [] Select All
    # [] (Root)
    # [] src
    # [] src/bin
    # And the value will be the actual path
    # e.g. (Root) -> "."
    choices = [("Select All", "ALL")] + [
        (p if p != "." else "(Root)", p) for p in candidates
    ]

    questions = [
        inquirer.Checkbox(
            "Modules",
            message="Make your selection with [SPACEBAR], then hit [ENTER] to submit",
            choices=choices,
        ),
    ]

    # This will contain just the indexes in the above choices list of tuples
    answers = inquirer.prompt(questions, theme=GreenPassion())

    selection = answers["Modules"]

    # Just return the candidates list
    if "ALL" in selection:
        return candidates

    return selection


def make_language_selection() -> SupportedLanguages:
    """
    Interactively prompts the user to select a supported programming language.

    This is invoked when the user does not provide the `--language` argument via the CLI.
    It displays a list of languages defined in `SupportedLanguages`.

    Returns:
        SupportedLanguages: The enum member corresponding to the user's selection.
    """

    pr(
        "\n[bold green]Select the programming language for which to generate the bridge.[/bold green]"
    )
    questions = [
        inquirer.List(
            "language",
            message="Hit [ENTER] to make your selection",
            choices=[l.value for l in SupportedLanguages],
        ),
    ]

    answers = inquirer.prompt(questions, theme=GreenPassion())
    return SupportedLanguages(answers["language"])


def get_final_inventory_file(
    base_path: Path, scopes: list[str], language: SupportedLanguages
) -> tuple[Path, Path, int, int]:
    """
    Filters the repository files into two distinct categories: Language files and Context files.

    This function runs a filtered `git ls-files` command scoped to the user-selected directories.
    It iterates through the file stream and assigns files to temporary inventory lists based on:
    1.  **Language Files:** Files matching the selected language's extensions (e.g., `.ts`, `.py`).
        These will later be processed by ctags.
    2.  **Context Files:** High-value text files (e.g., `README.md`, `package.json`) or universal
        configuration files defined in `UNIVERSAL_CONTEXT_FILES`. These will be read in full.

    Args:
        base_path (Path): The absolute root path of the repository.
        scopes (list[str]): A list of relative paths (modules) to restrict the git scan to.
        language (SupportedLanguages): The target language, used to determine valid code extensions.

    Returns:
        tuple[Path, Path, int, int]: A tuple containing:
            1. Path to the temporary file listing all valid Language files.
            2. Path to the temporary file listing all valid Context files.
            3. The count of Language files found.
            4. The count of Context files found.
    """

    pr("\n[bold cyan]🔍 Sifting through your codebase...[/bold cyan]")

    # Get the allowed extensions (e.g., {'.js', '.ts'})
    allowed_extensions = LANGUAGES_HEURISTICS[language]["extensions"]

    # Create the fast lookup set for the Reader (O(1) checks)
    # This is what we pass to read_file_content_smart
    tier_1_set: frozenset[str] = (
        frozenset(UNIVERSAL_CONTEXT_FILES) | LANGUAGES_HEURISTICS[language]["manifests"]
    )

    # Construct the command: git ls-files ... -- path1 path2
    # The "--" separator tells git "everything after this is a path"
    cmd = [
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
    ] + scopes

    total_files = count_git_files(base_path, cmd)

    lang_file_count = 0
    ctx_file_count = 0

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, encoding="utf-8"
    ) as lang_file, tempfile.NamedTemporaryFile(
        mode="w", delete=False, encoding="utf-8"
    ) as context_file:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(
                "[cyan]Scanning files and applying language filter...",
                total=total_files,
            )

            # Stream the results
            with subprocess.Popen(
                cmd,
                cwd=base_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            ) as process:
                if process.stdout:
                    for file_path in process.stdout:
                        file_path_obj = Path(file_path.strip())
                        file_name = file_path_obj.name.lower()

                        # Advance the raw counter
                        progress.update(task, advance=1)

                        # SIEVE 2: Extension Check
                        # Check if file ends with one of our valid extensions
                        # We use endswith because extensions usually include the dot
                        if file_path_obj.suffix.lower() in allowed_extensions:
                            lang_file_count += 1
                            lang_file.write(f"{file_path}\n")

                        elif (
                            file_name in tier_1_set
                            or "readme" in file_name
                            or file_path_obj.stem.lower() == "readme"
                            or file_path_obj.suffix.lower() == ".md"
                        ):
                            ctx_file_count += 1
                            context_file.write(f"{file_path}\n")
                        else:
                            continue

                        progress.update(
                            task,
                            description=f"[cyan]Kept {lang_file_count + ctx_file_count} {language} files...",
                        )

                process.wait()

            # Final update
            progress.update(
                task,
                description=f"[green]✅ Found {lang_file_count + ctx_file_count} valid files",
                completed=total_files,
            )

        return (
            Path(lang_file.name),
            Path(context_file.name),
            lang_file_count,
            ctx_file_count,
        )


def generate_tags_jsonl(
    base_path: Path,
    inventory_path: Path,
    context_path: Path,
    lang_file_count: int,
    ctx_file_count: int,
    language: SupportedLanguages,
) -> Path:
    """
    Generates the final JSONL payload containing file contents and code symbols.

    This function acts as the final assembly line. It performs two main phases:
    1.  **Context Phase:** Reads the full content of "Context Files" (identified in `get_final_inventory_file`).
        It prioritizes specific files (like manifests) and writes them to the output first.
    2.  **Tags Phase:** Invokes `run_ctags` to extract symbols from the "Language Files" listed
        in the inventory path.

    Args:
        base_path (Path): The absolute root path of the repository.
        inventory_path (Path): Path to the temporary file listing language-specific source files.
        context_path (Path): Path to the temporary file listing context/config files.
        lang_file_count (int): Total number of language files to process (for progress bars).
        ctx_file_count (int): Total number of context files to process (for progress bars).
        language (SupportedLanguages): The target language (used to prioritize specific manifests).

    Returns:
        Path: The file path to the generated `sential_payload.jsonl` in the system temp directory.
    """

    output_path = Path(tempfile.gettempdir()) / "sential_payload.jsonl"

    pr("\n[bold magenta]📄  Reading context files...[/bold magenta]")
    # Create the Ordered List for the Writer (Preserve Priority)
    # We concatenate the tuples, then use dict.fromkeys to dedup while keeping order.
    # This is O(N) and extremely fast.
    ordered_candidates = list(
        dict.fromkeys(
            UNIVERSAL_CONTEXT_FILES + tuple(LANGUAGES_HEURISTICS[language]["manifests"])
        )
    )

    success = False

    try:

        with open(output_path, "w", encoding="utf-8") as out_f:

            # --- PHASE 1: CONTEXT FILES (Full Content) ---

            # A. Load valid context files found by Git into a set
            valid_context_path_objs: set[Path] = set()
            with open(context_path, "r", encoding="utf-8") as f:
                valid_context_path_objs = {
                    Path(file_path.strip()) for file_path in f if file_path.strip()
                }

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:

                task = progress.add_task(
                    f"[magenta]Reading from {ctx_file_count} context files...",
                    total=ctx_file_count,
                )
                # B. The Priority Pass (Write the VIPs first)
                # We take each candidate in order, maintaining prio
                # candidates are names not relative paths
                for candidate in ordered_candidates:
                    # Find matches for this candidate
                    # We create a list of matches so we don't modify the set while iterating
                    matches: list[Path] = []
                    for ctx_file_path_obj in valid_context_path_objs:

                        if ctx_file_path_obj.name.lower() == candidate.lower():
                            matches.append(ctx_file_path_obj)

                    # Sort matches by depth (Root files first!)
                    # "package.json" (depth 0) comes before "backend/package.json" (depth 1)
                    matches.sort(key=lambda p: len(p.parents))

                    # Write them and remove from the pool
                    if matches:
                        for match in matches:
                            full_path = base_path / match
                            content = read_file_content(full_path, True)
                            if content:
                                ctx_record = {
                                    "path": str(match),
                                    "type": "context_file",
                                    "content": content,
                                }
                                out_f.write(json.dumps(ctx_record) + "\n")
                                progress.update(
                                    task,
                                    description=f"[cyan]Included {match}...",
                                    advance=1,
                                )

                            # Remove from the main set so it's not handled again
                            valid_context_path_objs.remove(match)

                # We handle whatever was left, anything that didn't match prev step
                leftovers = sorted(
                    list(valid_context_path_objs), key=lambda p: len(p.parents)
                )
                for leftover in leftovers:
                    full_path = base_path / leftover
                    content = read_file_content(full_path, True)

                    if content:
                        ctx_record = {
                            "path": str(leftover),
                            "type": "context_file",
                            "content": content,
                        }
                        out_f.write(json.dumps(ctx_record) + "\n")
                        progress.update(
                            task, description=f"[cyan]Included {leftover}...", advance=1
                        )
                progress.update(
                    task,
                    description=f"[green]✅ Processed {ctx_file_count} context files",
                    completed=ctx_file_count,
                )

            # --- PHASE 2: PROCESS LANG FILES CTAGS ---
            run_ctags(base_path, inventory_path, out_f, lang_file_count)
        success = True

    except KeyboardInterrupt as exc:
        pr("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit() from exc
    except Exception as e:
        pr(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit()

    finally:
        # Always clean up these temp files
        inventory_path.unlink(missing_ok=True)
        context_path.unlink(missing_ok=True)

        if not success:
            output_path.unlink(missing_ok=True)

    return output_path


def run_ctags(
    base_path: Path,
    inventory_path: Path,
    out_f: io.TextIOWrapper,
    lang_file_count: int,
):
    """
    Executes Universal Ctags on the provided inventory of files and streams the output to JSONL.

    This function streams file paths from `inventory_path` into the `ctags` subprocess via stdin.
    It parses the JSON output from ctags, aggregates symbols (tags) by file path, and writes
    a compressed record (path + list of tags) to the open output file handle `out_f`.

    Args:
        base_path (Path): The working directory for the ctags subprocess.
        inventory_path (Path): Path to the temporary file containing the list of source files to scan.
        out_f (io.TextIOWrapper): An open file handle (write mode) where the JSONL records will be written.
        lang_file_count (int): The total number of files to process, used for the progress bar.
    """

    pr("\n[bold magenta]🏷️  Extracting code symbols...[/bold magenta]")

    ctags = get_ctags_path()
    cmd = [
        ctags,
        "--output-format=json",
        "--sort=no",
        "--fields=+n",
        "-f",
        "-",
        "-L",
        "-",
    ]

    # We accumulate the tags for the current file only
    current_file_path = None
    current_tags: list[str] = []
    tag_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:

        task = progress.add_task(
            f"[magenta]Parsing symbols from {lang_file_count} files...",
            total=lang_file_count,
        )

        with open(inventory_path, "r", encoding="utf-8") as in_f:
            # Use Popen to stream the output
            with subprocess.Popen(
                cmd,
                cwd=base_path,
                stdin=in_f,  # Feed the file list via stdin
                stdout=subprocess.PIPE,  # Catch output via pipe
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            ) as process:

                if process.stdout:
                    for line in process.stdout:
                        try:
                            tag = json.loads(line)
                            path = tag.get("path")
                            kind = tag.get("kind")
                            name = tag.get("name")

                            if not path or not name or kind not in CTAGS_KINDS:
                                continue

                            if path != current_file_path:
                                if current_file_path:
                                    record = {
                                        "path": current_file_path,
                                        "tags": current_tags,
                                    }
                                    out_f.write(json.dumps(record) + "\n")
                                    progress.update(task, advance=1)
                                # Reset for new file
                                current_file_path = path
                                current_tags = []

                            # Add tag to current buffer
                            current_tags.append(f"{kind} {name}")
                            tag_count += 1

                            # Tick the spinner occasionally
                            if tag_count % 10 == 0:
                                progress.update(
                                    task,
                                    description=f"[magenta]Extracted {tag_count} symbols...",
                                )

                        except json.JSONDecodeError:
                            continue

                    # Write the last file's tags if any
                    if current_file_path:
                        record = {
                            "path": current_file_path,
                            "tags": current_tags,
                        }
                        out_f.write(json.dumps(record) + "\n")

        progress.update(
            task,
            description=f"[green]✅ Extracted {tag_count} symbols",
            completed=lang_file_count,
        )


def count_git_files(base_path: Path, cmd: list[str]) -> int:
    """
    Efficiently counts the number of lines (files) in a Git command output.

    This function executes the provided command and streams the output to count newlines
    without loading the entire output into memory. This is used to calculate totals for
    progress bars before processing begins.

    Args:
        base_path (Path): The directory in which to execute the command.
        cmd (list[str]): The command and its arguments as a list (e.g., `["git", "ls-files"]`).

    Returns:
        int: The total number of lines/files returned by the command.
    """

    count = 0
    # Use Popen to open a pipe, not a buffer
    with subprocess.Popen(
        cmd,
        cwd=base_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,  # Line buffered
    ) as process:

        # Iterate over the stream directly
        if process.stdout:
            for _ in process.stdout:
                count += 1

    return count


def read_file_content(file_path: Path, is_tier_1: bool = False) -> str:
    """
    Reads the text content of a file with safety checks and intelligent truncation.

    Binary files are automatically detected and skipped. Text files are read up to a specific
    character limit based on their importance "Tier".
    - **Tier 1 (True):** Critical context files (Manifests, Docs). Limit: 100k chars.
    - **Tier 2 (False):** Standard files. Limit: 50k chars.

    Args:
        file_path (Path): The absolute path to the file to read.
        is_tier_1 (bool): If True, applies a higher character limit (100k). If False,
            applies the standard limit (50k). Defaults to False.

    Returns:
        str: The content of the file. If the file is binary, non-existent, or an error occurs,
        returns an empty string. If the content exceeds the limit, it is truncated with a notice.
    """

    limit = 100_000 if is_tier_1 else 50_000

    if not file_path.is_file():
        return ""

    # We skip binary files
    if is_binary_file(file_path):
        return ""

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            # We read limit + 1 so we KNOW if there was more left behind
            content = f.read(limit + 1)

            if len(content) > limit:
                return (
                    content[:limit]
                    + f"\n\n... [TRUNCATED BY SENTIAL: File exceeded {limit} chars] ..."
                )

            return content
    except OSError:
        return ""


if __name__ == "__main__":
    app()
