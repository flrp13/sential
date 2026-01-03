"""
Code symbol extraction and payload generation module.

This module orchestrates the final assembly of the Sential payload by reading
context files in full and extracting code symbols via Universal Ctags. It generates
a JSONL file containing both full file contents (for context) and symbol metadata
(for code structure understanding).
"""

import io
import json
import subprocess
import tempfile
from pathlib import Path
import typer
from rich import print as pr
from adapters.ctags import get_ctags_path
from constants import (
    CTAGS_KINDS,
    UNIVERSAL_CONTEXT_FILES,
    LANGUAGES_HEURISTICS,
    SupportedLanguage,
)
from core.models import InventoryResult, RecordType
from ui.progress import ProgressState, create_progress, create_task, update_progress
from utils import read_file_content


def generate_tags_jsonl(
    base_path: Path,
    inventory_result: InventoryResult,
    language: SupportedLanguage,
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
        source_path (Path): Path to the temporary file listing language-specific source files.
        context_path (Path): Path to the temporary file listing context/config files.
        lang_file_count (int): Total number of language files to process (for progress bars).
        ctx_file_count (int): Total number of context files to process (for progress bars).
        language (SupportedLanguages): The target language (used to prioritize specific manifests).

    Returns:
        Path: The file path to the generated `sential_payload.jsonl` in the system temp directory.
    """

    source_path = inventory_result.source_inventory_path
    context_path = inventory_result.context_inventory_path
    lang_file_count = inventory_result.stats.language_files
    ctx_file_count = inventory_result.stats.context_files

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

            with create_progress() as progress:
                task = create_task(
                    progress,
                    f"Reading from {ctx_file_count} context files...",
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
                                    "type": RecordType.CONTEXT_FILE,
                                    "content": content,
                                }
                                out_f.write(json.dumps(ctx_record) + "\n")
                                update_progress(
                                    progress,
                                    task,
                                    ProgressState.IN_PROGRESS,
                                    description=f"Included {match}...",
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
                            "type": RecordType.CONTEXT_FILE,
                            "content": content,
                        }
                        out_f.write(json.dumps(ctx_record) + "\n")
                        update_progress(
                            progress,
                            task,
                            ProgressState.IN_PROGRESS,
                            description=f"Included {leftover}...",
                            advance=1,
                        )
                update_progress(
                    progress,
                    task,
                    ProgressState.COMPLETE,
                    description=f"✅ Processed {ctx_file_count} context files",
                    completed=ctx_file_count,
                )

            # --- PHASE 2: PROCESS LANG FILES CTAGS ---
            run_ctags(base_path, source_path, out_f, lang_file_count)
        success = True

    except KeyboardInterrupt as exc:
        pr("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit() from exc
    except Exception as e:
        pr(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit()

    finally:
        # Clean up output file only if generation failed
        # Temp inventory files (source_path, context_path) are cleaned up by FileInventoryWriter context manager
        if not success:
            output_path.unlink(missing_ok=True)

    return output_path


def run_ctags(
    base_path: Path,
    inventory_path: Path,
    out_f: io.TextIOWrapper,
    lang_file_count: int,
) -> None:
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

    ctags = str(get_ctags_path())
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

    with create_progress() as progress:

        task = create_task(
            progress,
            f"Parsing symbols from {lang_file_count} files...",
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
                                    update_progress(progress, task, advance=1)
                                # Reset for new file
                                current_file_path = path
                                current_tags = []

                            # Add tag to current buffer
                            current_tags.append(f"{kind} {name}")
                            tag_count += 1

                            # Tick the spinner occasionally
                            if tag_count % 10 == 0:
                                update_progress(
                                    progress,
                                    task,
                                    ProgressState.IN_PROGRESS,
                                    description=f"Extracted {tag_count} symbols...",
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

        update_progress(
            progress,
            task,
            ProgressState.COMPLETE,
            description=f"✅ Extracted {tag_count} symbols",
            completed=lang_file_count,
        )
