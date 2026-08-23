# atspi-tree-dump

atspi-tree-dump dumps the AT-SPI accessibility tree of every top-level window
on a Linux desktop into JSON files, one file per window, and writes a fully
filtered token-lean flat record list for each window. The result is meant to
be read by agent systems to understand what is on screen: which elements
exist, how they are grouped, and in which state they are.

Primary target platform: Kubuntu with KDE, Wayland.

## Requirements

Python 3 with PyGObject and the AT-SPI bindings (gi.Atspi). The at-spi bus
must be running. Qt and KDE applications expose their accessibility tree only
when accessibility is enabled: set AccessibilityEnabled=true in the KDE group
of ~/.config/kdeglobals and restart the application, otherwise its window tree
stays empty.

## Usage

python3 atspi_dump_json.py

The script walks the AT-SPI desktop, finds every top-level window of every
application, and writes:

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
hooks/pre-commit — bumps the patch version on every commit.
src/atspi_tree_dump/ — version source and the bump_version module.
dumps/ — generated snapshots, ignored by git.

## Version

The current version is 0.1.7. The pre-commit hook reads the version from
src/atspi_tree_dump/__init__.py, increments the patch step and stages the
change, so the version grows with each commit.

## License

See LICENSE.
