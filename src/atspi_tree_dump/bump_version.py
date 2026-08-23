"""Version bumping for the repository.

The pre-commit hook (hooks/pre-commit) runs this module before every
commit so the version grows with each commit. The single version source
is src/atspi_tree_dump/__init__.py. A missing version line is left
untouched: the hook must never invent content.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_VERSION_PATTERN = re.compile(r'__version__ = "([^"]+)"')
_PACKAGE_VERSION_FILE = Path("src/atspi_tree_dump/__init__.py")


def read_current_version(version_file: Path) -> str:
    """The version string from the __version__ line of the package file."""

    text = version_file.read_text(encoding="utf-8")
    match = _VERSION_PATTERN.search(text)
    if match is None:
        raise ValueError(f"version string not found in {version_file}")
    return match.group(1)


def next_patch_version(version: str) -> str:
    """The next patch version of a dotted triple; ValueError on any other shape."""

    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid version: {version}")
    major, minor, patch = (int(part) for part in parts)
    return f"{major}.{minor}.{patch + 1}"


def set_version_in_file(path: Path, needle: str, slide: str) -> bool:
    """Replace the version line of path with slide; return whether it changed.

    A missing version line stays untouched: only a line that contains the
    needle is replaced, so the file never gains an orphan line at the end.
    """

    text = path.read_text(encoding="utf-8")
    changed = False
    lines = []
    for line in text.splitlines(keepends=True):
        if needle in line:
            lines.append(slide + "\n")
            changed = True
        else:
            lines.append(line)
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def bump_version_in_repo(root: Path) -> str:
    """Bump the patch version in the package file and return the new version."""

    version_file = root / _PACKAGE_VERSION_FILE
    new_version = next_patch_version(read_current_version(version_file))
    set_version_in_file(
        version_file, '__version__ = "', f'__version__ = "{new_version}"'
    )
    return new_version


def main(argv: list[str] | None = None) -> int:
    """Bump the version in the repository and print the new version."""

    parser = argparse.ArgumentParser(
        description="Bump the atspi-tree-dump patch version in the repository."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="print the next version without writing any file",
    )
    args = parser.parse_args(argv)
    if args.print_only:
        version_file = args.root / _PACKAGE_VERSION_FILE
        new_version = next_patch_version(read_current_version(version_file))
    else:
        new_version = bump_version_in_repo(args.root)
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
