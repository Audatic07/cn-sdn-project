#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Cleaning previous Mininet state..."
sudo mn -c >/dev/null 2>&1 || true

echo "Starting Mininet topology..."
sudo python3 topology/port_monitor_topology.py
