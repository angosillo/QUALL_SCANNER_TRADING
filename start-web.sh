#!/bin/bash
export PYTHONPATH=/home/administrator/momo-scanner/src
exec python3 -m momo web --host 0.0.0.0 --port 8000
