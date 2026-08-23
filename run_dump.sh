#!/usr/bin/env bash
# Wrapper for the Meta+Ctrl+Q global shortcut. Runs the AT-SPI dump script from
# this repository, then shows a one-second notification with the result.
cd /home/i/Downloads/atspi_dump
uv run atspi_dump_json.py
status=$?
if [ "$status" -eq 0 ]; then
    notify-send -t 1000 "AT-SPI dump" "Dump saved"
else
    notify-send -t 1000 "AT-SPI dump" "Dump failed"
fi
exit "$status"
