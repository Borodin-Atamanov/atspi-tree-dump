#!/usr/bin/env bash
# Wrapper for the Meta+Ctrl+Q global shortcut. Runs the AT-SPI dump script from
# this repository, then shows a one-second notification with the result.
cd /home/i/Downloads/atspi_dump
output=$(uv run atspi_dump_json.py 2>&1)
status=$?
notify-send -t 3777 "AT-SPI dump" "$output"
exit "$status"
