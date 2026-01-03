from pathlib import Path
import inquirer  # type: ignore
from inquirer.themes import GreenPassion  # type: ignore
from rich import print as pr
import typer

# Note: You will need to import get_focused_inventory from core.discovery here
from constants import SupportedLanguage
from core.discovery import get_focused_inventory


def select_scope(path: Path, language: SupportedLanguage) -> list[str]:
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
        only one module is found. Nested child modules are automatically filtered out
        if their parent is already selected.

    Raises:
        typer.Exit: If no modules matching the language heuristics are found in the path.
    """

    candidates = sorted(
        list(p for p in get_focused_inventory(path, SupportedLanguage(language)))
    )

    if not candidates:
        pr(
            f"[bold red]Couldn't find any[/bold red] [italic green]{language}[/italic green] [bold red]modules in path:[/bold red] [italic green]{path}[/italic green]"
        )
        raise typer.Exit()

    if len(candidates) == 1:
        return [str(candidates[0])]

    pr(
        "[bold green]Sential found multiple modules. Which ones should we focus on?[/bold green]\n"
    )

    # Build choices: if "." is in candidates, display it as "Select All"
    # Otherwise, display paths as-is

    choices: list[tuple[str, Path]] = []
    if Path(".") in candidates:
        choices = [("Select All (Include everything)", Path("."))]
        candidates.remove(Path("."))  # Remove from list to avoid duplication
    file_tree_builder = FileTreeBuilder(candidates)
    choices += file_tree_builder.render()

    questions = [
        inquirer.Checkbox(
            "Modules",
            message="Make your selection with [SPACEBAR], then hit [ENTER] to submit",
            choices=choices,
        ),
    ]

    answers = inquirer.prompt(questions, theme=GreenPassion())
    if not answers:
        raise typer.Exit()

    selection: list[Path] = answers["Modules"]

    # If "." (Select All) is selected, return it
    if Path(".") in selection:
        return ["."]

    # Filter out nested child modules if their parent is already selected
    filtered_selection: list[str] = []

    # If a parent of current scope_path is already in filtered_selection
    # we don't need to add its children, since it's redundant
    # for this logic to work we rely on the fact that candidates
    # is sorted ascending
    for scope_path in selection:
        is_parent_in_filtered_selection = False
        for p in filtered_selection:
            try:
                scope_path.relative_to(Path(p))
                is_parent_in_filtered_selection = True
            except ValueError:
                pass

        if not is_parent_in_filtered_selection:
            filtered_selection.append(str(scope_path))

    return filtered_selection


def make_language_selection() -> SupportedLanguage:
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
            choices=[l for l in SupportedLanguage],
        ),
    ]

    answers = inquirer.prompt(questions, theme=GreenPassion())

    if not answers:
        raise typer.Exit()

    return SupportedLanguage(answers["language"])


class FileTreeBuilder:
    """
    Builds a hierarchical tree structure from a list of file paths for display in prompts.

    This class takes a list of Path objects and organizes them into a tree structure
    where parent-child relationships are determined by path hierarchy. It then renders
    this tree as a list of formatted display strings suitable for use in interactive
    prompts (e.g., with inquirer).

    The tree visualization uses ASCII box-drawing characters (├──, └──, │) to show
    the hierarchical relationships between paths, making it easier for users to
    understand the module structure when selecting scopes.

    Attributes:
        paths: List of Path objects to build the tree from. Should be sorted in
            ascending alphabetical order for correct tree construction.
    """

    class _TreeNode:
        """
        Internal node class representing a single path in the tree structure.

        Each node contains a path and a list of its child nodes, forming a tree
        structure that represents the hierarchical relationships between paths.

        Attributes:
            path: The Path object this node represents.
            children: List of child TreeNode objects that are nested under this path.
        """

        def __init__(self, path: Path):
            """
            Initialize a tree node with the given path.

            Args:
                path: The Path object to associate with this node.
            """
            self.path = path
            self.children: list[FileTreeBuilder._TreeNode] = []

    def __init__(self, paths: list[Path]):
        """
        Initialize the FileTreeBuilder with a list of paths.

        Args:
            paths: List of Path objects to build the tree from. Should be sorted
                in ascending alphabetical order for optimal tree construction.
        """
        self.paths = paths

    def render(self) -> list[tuple[str, Path]]:
        """
        Build and render the tree structure as formatted display choices.

        This method constructs the tree hierarchy from the paths and then formats
        it as a list of tuples suitable for use in interactive prompts. Each tuple
        contains a formatted display string (with tree characters) and the original
        Path object.

        Returns:
            list[tuple[str, Path]]: List of tuples where each tuple contains:
                - A formatted display string showing the tree structure (e.g., "├── src/app")
                - The original Path object for the selection value
        """
        roots = self._build_tree_choices()
        return self._render_helper(roots)

    def _render_helper(
        self, nodes: list[FileTreeBuilder._TreeNode], prefix: str = ""
    ) -> list[tuple[str, Path]]:
        """
        Recursively render tree nodes with proper indentation and tree characters.

        This helper method traverses the tree structure and formats each node with
        appropriate tree-drawing characters (├──, └──, │) to show parent-child
        relationships. The prefix parameter accumulates the vertical lines and
        spacing needed to maintain proper tree visualization.

        Args:
            nodes: List of TreeNode objects to render at the current level.
            prefix: String prefix for indentation and vertical lines. Accumulates
                as the method recurses deeper into the tree.

        Returns:
            list[tuple[str, Path]]: List of formatted display tuples for all nodes
                in the subtree rooted at the given nodes.
        """
        choices: list[tuple[str, Path]] = []
        count = len(nodes)

        for i, node in enumerate(nodes):
            is_last = i == count - 1
            connector = "└── " if is_last else "├── "
            display_name = f"{prefix}{connector}{node.path}"
            choices.append((display_name, node.path))

            child_prefix = prefix + ("    " if is_last else "│   ")
            choices.extend(self._render_helper(node.children, child_prefix))
        return choices

    def _build_tree_choices(self) -> list[FileTreeBuilder._TreeNode]:
        """
        Build a tree structure from the list of paths.

        This method constructs a hierarchical tree where parent-child relationships
        are determined by path ancestry. It uses a stack-based algorithm to efficiently
        build the tree structure by maintaining a stack of ancestor nodes as it
        processes paths in order.

        The method expects paths to be sorted in ascending alphabetical order for
        correct tree construction. When a path is processed, it checks if it's a
        child of the most recent ancestor on the stack. If not, it pops ancestors
        from the stack until it finds the correct parent or reaches the root level.

        Returns:
            list[FileTreeBuilder._TreeNode]: List of root nodes in the tree structure.
                Each root node represents a top-level path with its nested children
                attached as child nodes.
        """
        stack: list[FileTreeBuilder._TreeNode] = []
        roots: list[FileTreeBuilder._TreeNode] = []

        for path in self.paths:
            node = FileTreeBuilder._TreeNode(path)

            while stack:
                try:
                    path.relative_to(stack[-1].path)
                    break
                except ValueError:
                    stack.pop()

            if stack:
                stack[-1].children.append(node)
            else:
                roots.append(node)

            stack.append(node)

        return roots
