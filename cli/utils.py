"""
Utility functions
"""

from rich.console import Console
from rich.style import Style

console = Console()


def debug(
    *values: object,
    sep: str = " ",
    end: str = "\n",
) -> None:
    print("Sssssssss")
    """Print debug message with orange bold formatting."""
    if not values:
        print(end=end)
        return

    # Convert all values to strings
    str_values = [str(v) for v in values]

    # Join with separator
    message = sep.join(str_values)

    # Print with formatting
    console.print(f"DEBUG: {message}", end=end, style="orange1")
