"""
This is a simple CLI tool that receives a path to a folder and lists all the files in it.
"""

import os
from pathlib import Path
from typing import TypedDict, List, Annotated
import typer
from rich import print as pr
import inquirer

from constants import (
    SupportedLanguages,
    LANGUAGES_HEURISTICS,
    IGNORE_DIRS,
)
from utils import debug

FilePath = Annotated[str, "A valid filesystem path"]


class CandidateRoot(TypedDict):
    """Type definition for a candidate module root."""

    path: FilePath
    type: str
    manifest: str
    depth: int


app = typer.Typer()


@app.command()
def main(
    path: Annotated[
        FilePath,
        typer.Option(
            help="Root path from which Sential will start identifying modules"
        ),
    ] = ".",
    language: Annotated[
        str,
        typer.Option(
            help=f"Available languages: {', '.join([l.value for l in SupportedLanguages])}"
        ),
    ] = "",
):
    """Main entry point"""
    # Validate path is directory
    if not os.path.isdir(path):
        pr(
            f"[red]Error:[/red] Not a valid path or not a directory: [green]'{path}'[/green]"
        )
        raise typer.Exit()

    # Validate directory not empty
    if len(os.listdir(path)) == 0:
        pr(f"[red]Error:[/red] Empty directory: [green]'{path}'[/green]")
        raise typer.Exit()

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
    candidates = scan_repo_structure(path, SupportedLanguages(language))
    scopes = select_scope(candidates, path, SupportedLanguages(language))
    print(scopes)


def scan_repo_structure(
    base_path: FilePath, language: SupportedLanguages
) -> List[CandidateRoot]:
    """
    Walks the repo and builds a 'Heat Map' of potential modules.
    Returns a list of 'Candidate Roots'.
    """
    candidates: List[CandidateRoot] = []
    base = Path(base_path).resolve()

    for root, dirs, files in os.walk(base):
        # MODIFY dirs IN-PLACE (Pruning)
        # This prevents os.walk from entering ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        # Get path relative to root (not fully qualified)
        rel_path = Path(root).relative_to(base)

        # Go through all files in current dir
        # save whichever are considered manifests
        found_manifests = [
            f for f in files if f in LANGUAGES_HEURISTICS[language]["manifests"]
        ]
        if found_manifests:
            # Each of the manifests have the same weight so just pick first
            first_manifest = found_manifests[0]
            candidate: CandidateRoot = {
                "path": str(rel_path),
                "type": language.value,
                "manifest": first_manifest,
                "depth": len(rel_path.parts),
            }
            candidates.append(candidate)
    return candidates


def select_scope(
    candidates: List[CandidateRoot], path: FilePath, language: SupportedLanguages
) -> List[FilePath]:
    if not candidates:
        pr(
            f"[bold red]Couldn't find any[/bold red] [italic green]{language.value}[/italic green] [bold red]modules in path:[/bold red] [italic green]{path}[/italic green]"
        )
        raise typer.Exit()

    if len(candidates) == 1:
        return [candidates[0]["path"]]

    pr(
        "[bold green]Sential found multiple modules. Which ones should we focus on?[/bold green]"
    )
    choices = ["Select All"] + [
        f"{idx+1}. {c['path']}" for idx, c in enumerate(candidates)
    ]
    questions = [
        inquirer.Checkbox(
            "Modules",
            message="Make your selection with [SPACEBAR], then hit [ENTER] to submit",
            choices=choices,
        ),
    ]
    answers = inquirer.prompt(questions)

    if "Select All" in answers["Modules"]:
        return [c["path"] for c in candidates]

    selected_indices = [
        int(x.split(".")[0]) - 1
        for x in answers["Modules"]
        if x.split(".")[0].isdigit()
    ]

    debug(answers["Modules"])

    return [candidates[i]["path"] for i in selected_indices if 0 <= i < len(candidates)]


def make_language_selection() -> SupportedLanguages:
    """
    Shows the user a list of supported programming languages
    from which they can select a single option
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

    answers = inquirer.prompt(questions)
    return SupportedLanguages(answers["language"])


if __name__ == "__main__":
    app()
