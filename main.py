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
import pathlib
from typing import Annotated, Optional
import typer
from rich import print as pr
from adapters.git import GitClient
from constants import SupportedLanguage
from core.discovery import FileInventoryWriter
from core.exceptions import EmptyInventoryError, TempFileError
from core.extraction import generate_tags_jsonl
from ui.progress_callback import RichProgressCallback
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
    ] = pathlib.Path().resolve(),  # If not provided, chose the path where the user ran the command
    language: Annotated[
        Optional[str],
        typer.Option(help=f"Available languages: {', '.join(list(SupportedLanguage))}"),
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

    # Validate language passed by user
    # If not passed, open language selection
    try:
        language = normalize_language(language)
    except ValueError:
        pr(f"\n[red bold]Not a valid language: {language}")
        language = make_language_selection()

    pr(f"\n[green]Language selected: {language}...[/green]\n")
    pr(f"[green]Scanning: {path}...[/green]\n")

    scopes = select_scope(path, language)
    try:
        with FileInventoryWriter(
            path, scopes, language, GitClient(path), RichProgressCallback()
        ) as writer:
            pr("\n[bold magenta]🔍 Sifting through your codebase...")
            inventory_result = writer.process()
            tags_map = generate_tags_jsonl(
                path,
                inventory_result,
                language,
            )
            print(tags_map)
    except EmptyInventoryError as e:
        print_empty_inventory_err(e, language)
    except TempFileError as e:
        print_temp_file_err(e)


def normalize_language(language: Optional[str]) -> SupportedLanguage:
    """
    Normalizes and validates a language string to a SupportedLanguage enum value.

    Performs case-insensitive matching against the supported languages and returns
    the matching enum value. If no language is provided (None or empty string) or
    the string doesn't match any supported language, raises ValueError.

    Args:
        language (Optional[str]): The language string to normalize. Can be None,
            empty, or a string representation of a supported language.

    Returns:
        SupportedLanguage: The matching SupportedLanguage enum value.

    Raises:
        ValueError: If no language is provided (None or empty string) or if the
            provided language string doesn't match any supported language
            (case-insensitive).
    """
    # Validate language selection
    if language:

        language = language.strip().lower()

        for l in SupportedLanguage:
            if l.lower() == language:
                return l
    raise ValueError


def print_empty_inventory_err(
    e: EmptyInventoryError, language: SupportedLanguage
) -> None:
    """
    Displays a user-friendly error message when no files are found.

    Prints formatted error messages to inform the user that no files matching
    the specified language were found in the selected scopes, along with
    helpful tips for resolving the issue.

    Args:
        e (EmptyInventoryError): The exception that was raised, containing
            error details.
        language (SupportedLanguage): The target language that was being scanned.

    Raises:
        typer.Exit: Always raises with exit code 1 to terminate the application.
    """
    pr("[yellow]⚠️  No files found[/yellow]")
    pr(
        f"No files matching [green]{language}[/green] were found in the selected scopes."
    )
    pr(
        "\n[yellow]Tip:[/yellow] Try selecting different scopes or verify the repository contains files for this language."
    )
    raise typer.Exit(code=1) from e


def print_temp_file_err(e: TempFileError) -> None:
    """
    Displays a user-friendly error message for temporary file operation failures.

    Prints formatted error messages to inform the user about workspace/temporary
    file issues, including diagnostic information for troubleshooting. This helps
    users understand and resolve filesystem permission or disk space problems.

    Args:
        e (TempFileError): The exception that was raised, containing error details
            and diagnostic information.

    Raises:
        typer.Exit: Always raises with exit code 1 to terminate the application.
    """
    pr("❌ [bold red]Workspace Error[/bold red]")
    pr("The app couldn't create the temporary files needed to run.")
    pr(
        "\n[yellow]Quick Fix:[/yellow] Ensure your temp folder is writable and you have free disk space."
    )

    pr("\n--- PLEASE REPORT THIS ---")
    pr(f"Error Context: {e}")
    pr(f"Diagnostics: {e.diagnostic_info}")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
