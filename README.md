# atspi-tree-dump

atspi-tree-dump dumps the AT-SPI accessibility tree of every top-level window
on a Linux desktop into JSON files, one file per window, and writes a fully
filtered token-lean flat record list for each window. The result is meant to
be read by agent systems to understand what is on screen: which elements
exist, how they are grouped, and in which state they are.

Primary target platform: Kubuntu with KDE, Wayland.

## Requirements

Tested on Kubuntu 26 with KDE and Wayland. The script needs the PyGObject and
AT-SPI bindings as system packages for the system Python:

sudo apt install python3-gi gir1.2-atspi-2.0

Qt and KDE applications expose their accessibility tree only when
accessibility is enabled. Turn it on with:

kwriteconfig6 --file kdeglobals --group KDE --key AccessibilityEnabled true

Then restart the application so it loads the accessibility bridge; without
this, its windows expose no elements to the script. These system packages are
not installed through uv: uv only manages the script's Python environment.

## Usage

uv venv --system-site-packages
uv run atspi_dump_json.py

The first command creates the project environment with access to the system
site packages, so the PyGObject and AT-SPI bindings are visible. The second
runs the script. uv tracks the project version, the Python requirement and the
dependency lock (pyproject.toml, uv.lock and .python-version). The script
walks the AT-SPI desktop, finds every top-level window of every application,
and writes:

1. dumps/<window>.json — the raw accessibility tree as-is.
2. dumps/<window>-filtered.json — the fully filtered flat record list.

An existing dumps directory is renamed to <creation-time>-dumps in the project
datetime format YYYY-MM-DD-HH-MM-SS before a new run, so past snapshots are
kept.

## Filtering

The raw tree is flattened into an ordered list of records with fields role,
name, checked and states. Meaningless wrappers are dropped, boilerplate states
are removed, radio-button ghosts are deleted, duplicate (role, name) pairs are
folded, and navigation list items are collapsed into a sidebar categories
node. Real switches with a checked field are never removed.

## Structure

AGENTS.md — mandatory rules for AI agents.
README.md — this file.
atspi_dump_json.py — the dump and filtering script.
hooks/pre-commit — bumps the patch version and refreshes the lock on every commit.
src/atspi_tree_dump/ — version source and the bump_version module.
pyproject.toml — uv project metadata with the dynamic version.
uv.lock — locked dependency versions.
.python-version — pinned Python version.
dumps/ — generated snapshots, ignored by git.

## License

See LICENSE.
