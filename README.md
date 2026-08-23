# atspi-tree-dump

Dumps the AT-SPI accessibility tree of every top-level window into per-window
JSON files and writes a fully filtered flat record list for each window.

## Requirements

Tested on Kubuntu 26 with KDE and Wayland.

sudo apt install python3-gi gir1.2-atspi-2.0

Qt and KDE applications expose their accessibility tree only when
accessibility is enabled. Turn it on with:

kwriteconfig6 --file kdeglobals --group KDE --key AccessibilityEnabled true

or set AccessibilityEnabled=true in the [KDE] group of ~/.config/kdeglobals.
Then restart the application; without this its windows expose no elements to
the script.

## Usage

uv venv --system-site-packages
uv run atspi_dump_json.py

Output in dumps/: <window>.json is the raw tree, <window>-filtered.json is the
filtered record list.

## Structure

AGENTS.md — mandatory rules for AI agents.
atspi_dump_json.py — the dump and filtering script.
hooks/pre-commit — bumps the patch version and refreshes the lock on every commit.
src/atspi_tree_dump/ — version source and the bump_version module.
pyproject.toml — uv project metadata with the dynamic version.
uv.lock — locked dependency versions.
.python-version — pinned Python version.
dumps/ — generated snapshots, ignored by git.

## License

See LICENSE.
