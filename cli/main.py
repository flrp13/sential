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

from pathlib import Path
from typing import Annotated, Optional
import typer
from rich import print as pr
from adapters.git import GitClient
from constants import SupportedLanguage
from core.discovery import FileInventoryWriter
from core.extraction import generate_tags_jsonl
from ui.prompts import make_language_selection, select_scope


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
        Optional[str],
        typer.Option(
            help=f"Available languages: {', '.join([l for l in SupportedLanguage])}"
        ),
    ] = None,
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
    git_client = GitClient(path)
    if not git_client.is_repo():
        pr(f"[red]Error:[/red] Not a git repository: [green]'{path}'[/green]")
        raise typer.Exit()

    try:
        language = _normalize_language(language)
    except ValueError as exc:
        pr(
            f"[red]Error:[/red] Selected language not supported ([green]'{language}'[/green]),\n run [italic]sential --help[/italic] to see a list of supported languages."
        )
        raise typer.Exit() from exc

    pr(f"\n[green]Language selected: {language}...[/green]\n")
    pr(f"[green]Scanning: {path}...[/green]\n")

    scopes = select_scope(path, language)
    with FileInventoryWriter(path, scopes, language) as writer:
        pr("\n[bold magenta]🔍 Sifting through your codebase...")
        inventory_result = writer.process()
        tags_map = generate_tags_jsonl(
            path,
            inventory_result,
            language,
        )
        print(tags_map)


def _normalize_language(language: Optional[str]) -> SupportedLanguage:
    # Validate language selection
    if not language or not language.strip():
        # If language not passed as arg, show options
        return make_language_selection()

    language = language.strip().lower()

    for l in SupportedLanguage:
        if l.lower() == language:
            return l

    raise ValueError


if __name__ == "__main__":
    app()
