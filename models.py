"""
Type definitions and data models used across the Sential CLI application.

This module contains shared type definitions including enums and TypedDict
structures that are used throughout the codebase for type safety and consistency.
"""

from enum import StrEnum
from typing import TypedDict


class SupportedLanguage(StrEnum):
    """
    Enumeration of programming languages supported by Sential.

    Each language value corresponds to a human-readable name that is used
    in user interfaces and language selection prompts. The enum values are
    used as keys in the LANGUAGES_HEURISTICS mapping to retrieve language-specific
    configuration (manifest files, file extensions, etc.).
    """

    PY = "Python"
    JS = "JavaScript/TypeScript"
    JAVA = "Java"
    CS = "C#"
    GO = "GO"
    CPP = "C/C++"


class LanguagesHeuristics(TypedDict):
    """
    Type definition for language-specific heuristics configuration.

    This TypedDict defines the structure used in LANGUAGES_HEURISTICS to store
    language-specific metadata that helps identify modules and filter files.

    Attributes:
        manifests: A frozen set of manifest file names (e.g., "package.json", "requirements.txt")
            that indicate the presence of a module or project in a directory.
        extensions: A frozen set of file extensions (e.g., ".py", ".ts") that identify
            source code files for the target language.
        signals: A frozen set of signal file names (e.g., "__init__.py", "index.js") that
            strongly indicate a module root, even without explicit manifests.
    """

    manifests: frozenset[str]
    extensions: frozenset[str]
    signals: frozenset[str]
