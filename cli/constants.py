from enum import StrEnum
from typing import Final, Mapping, TypedDict


class SupportedLanguages(StrEnum):
    PY = "Python"
    JS = "JavaScript/TypeScript"
    JAVA = "Java"
    CS = "C#"
    GO = "GO"
    CPP = "C/C++"


class LanguagesHeuristics(TypedDict):
    manifests: frozenset[str]
    extensions: frozenset[str]


LANGUAGES_HEURISTICS: Final[Mapping[SupportedLanguages, LanguagesHeuristics]] = {
    SupportedLanguages.PY: {
        "manifests": frozenset(
            {
                "requirements.txt",
                "pyproject.toml",
                "setup.py",
                "pipfile",
                "tox.ini",
            }
        ),
        "extensions": frozenset({".py", ".pyi"}),
    },
    SupportedLanguages.JS: {
        "manifests": frozenset(
            {
                "package.json",
                "deno.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "next.config.js",
                "vite.config.js",
                "tsconfig.json",
            }
        ),
        "extensions": frozenset(
            {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
        ),
    },
    SupportedLanguages.JAVA: {
        "manifests": frozenset(
            {
                "pom.xml",  # Maven
                "build.gradle",  # Gradle (Groovy)
                "build.gradle.kts",  # Gradle (Kotlin)
                "settings.gradle",
                "mvnw",  # Maven Wrapper
                "gradlew",  # Gradle Wrapper
            }
        ),
        "extensions": frozenset({".java", ".kt", ".scala", ".groovy"}),
    },
    SupportedLanguages.CS: {
        "manifests": frozenset(
            {
                ".csproj",
                ".sln",
                ".fsproj",
                ".vbproj",
                "global.json",
                "nuget.config",
            }
        ),
        "extensions": frozenset({".cs", ".fs", ".vb", ".cshtml", ".razor"}),
    },
    SupportedLanguages.GO: {
        "manifests": frozenset(
            {
                "go.mod",
                "go.sum",
                "go.work",
                "main.go",
            }
        ),
        "extensions": frozenset({".go"}),
    },
    SupportedLanguages.CPP: {
        "manifests": frozenset(
            {
                "cmakelists.txt",
                "makefile",
                "configure.ac",
                "meson.build",
                "conanfile.txt",
                "vcpkg.json",
                ".gitmodules",
            }
        ),
        "extensions": frozenset(
            {
                ".c",
                ".cpp",
                ".h",
                ".hpp",
                ".cc",
                ".hh",
                ".cxx",
                ".hxx",
                ".m",
                ".mm",
            }
        ),
    },
}

CTAGS_KINDS = frozenset(
    {
        # The Core Logic
        "class",
        "method",
        "function",
        # The Data Structures
        "struct",
        "enum",
        "union",
        "interface",
        "typedef",
        "type",
        # The Hierarchy (Crucial for C#/C++)
        "namespace",
        "module",
        "package",
    }
)

# A static list of files that, if they exist, define the "Soul" of a project.
# We check these regardless of the programming language.
UNIVERSAL_CONTEXT_FILES: tuple[str, ...] = (
    # Documentation & Intent (The "Why")
    "readme.md",
    "readme.txt",
    "architecture.md",
    "contributing.md",
    "design.md",
    # AI Specific Instructions (The "How" - Extremely High Signal)
    "claude.md",
    ".cursorrules",
    ".windsurfrules",
    # Environment / Config Templates (The "Infrastructure")
    ".env.example",
    ".env.template",
    "docker-compose.yml",
    "dockerfile",
    "makefile",
    "justfile",
    "rakefile",
    "procfile",
)
