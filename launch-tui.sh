#!/bin/bash
export TERM=xterm-256color
cd /home/administrator/momo-scanner || exit 1
PYTHONPATH=src exec python3 -m momo tui
