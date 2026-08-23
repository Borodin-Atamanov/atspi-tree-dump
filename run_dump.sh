#!/usr/bin/env bash
# Wrapper for the Meta+Ctrl+Q global shortcut. Runs the AT-SPI dump script from
# this repository, then shows a one-second notification with the result.
work_dir=${HOME}/Downloads/atspi_dump
mkdir -pv ${work_dir}
cd ${work_dir}
output=$(uv run atspi_dump_json.py 2>&1)
status=$?
notify-send -t 3777 "AT-SPI dump" "$output"
exit "$status"
