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
                "Pipfile",
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
                "NuGet.config",
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
                "CMakeLists.txt",
                "Makefile",
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

IGNORE_DIRS = {
    # Version control
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    ".fossil",
    # Python
    ".venv",
    "venv",
    "env",
    ".env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".coverage",
    ".hypothesis",
    ".ruff_cache",
    "htmlcov",
    # Node.js / JavaScript
    "node_modules",
    ".npm",
    ".yarn",
    ".yarn-cache",
    ".pnpm-store",
    ".next",
    ".nuxt",
    ".astro",
    # IDEs and editors
    ".idea",
    ".vscode",
    ".vs",
    ".eclipse",
    ".settings",
    ".metadata",
    ".sublime-project",
    ".sublime-workspace",
    ".vim",
    ".emacs.d",
    # Build artifacts and compiled code (common across languages)
    "build",
    "dist",
    "target",
    "out",
    "bin",
    "obj",
    ".gradle",
    ".mvn",
    "cmake-build-debug",
    "cmake-build-release",
    "cmake-build",
    ".deps",
    ".libs",
    "Debug",
    "Release",
    ".classpath",
    ".project",
    # Package managers and dependencies
    "vendor",
    ".bundle",
    "bower_components",
    ".cargo",
    # OS and system files
    ".DS_Store",
    "Thumbs.db",
    ".Spotlight-V100",
    ".Trashes",
    # Temporary and cache
    ".cache",
    ".tmp",
    ".temp",
    ".log",
    ".logs",
    "tmp",
    "temp",
    # Documentation builds
    "_build",
    ".doctrees",
    "site",
    # Infrastructure and deployment
    ".terraform",
    ".vagrant",
    ".docker",
    ".k8s",
}
