#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PORT_MONITOR_LOG="$ROOT_DIR/logs/port_events.log"
mkdir -p logs

POX_DIR="${POX_DIR:-$ROOT_DIR/pox}"

if [[ ! -f "$POX_DIR/pox.py" ]]; then
	echo "POX not found at: $POX_DIR"
	echo "Clone POX and retry:"
	echo "  cd $ROOT_DIR"
	echo "  git clone https://github.com/noxrepo/pox.git"
	exit 1
fi

mkdir -p "$POX_DIR/pox/ext"
touch "$POX_DIR/pox/ext/__init__.py"
ln -sfn "$ROOT_DIR/controller/port_status_monitor.py" "$POX_DIR/pox/ext/port_status_monitor.py"

echo "Starting POX controller (OpenFlow10)..."
cd "$POX_DIR"
./pox.py log.level --INFO openflow.of_01 --port=6653 forwarding.l2_learning ext.port_status_monitor
