#!/usr/bin/env python3
"""POX app for monitoring switch port status changes.

The component listens to OpenFlow events exposed by POX and maintains an
in-memory view of per-switch, per-port state. It also writes timestamped
status transitions to a log file for easy auditing.
"""

import os
from datetime import datetime

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str


log = core.getLogger()


class PortStatusMonitor(object):
    """POX OpenFlow 1.0 controller component for port-state monitoring.

    Internal state:
    - switches: map of raw datapath IDs to active connection objects.
    - port_state: map of string datapath IDs to {port_no: bool(is_up)} maps.
    """

    def __init__(self):
        # Two separate dictionaries are used intentionally:
        # - switches keeps live connection objects keyed by numeric DPID.
        # - port_state keeps a serializable/print-friendly snapshot keyed by
        #   string DPID, which is easier to log and compare in outputs.
        # Track active switch connections by numeric DPID.
        self.switches = {}
        # Track current known port state by display-friendly DPID string.
        self.port_state = {}

        # Allow log destination override, defaulting to project log path.
        self.log_path = os.environ.get("PORT_MONITOR_LOG", "logs/port_events.log")
        # Ensure the parent directory exists before writing log lines.
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

        # Register this object so POX dispatches OpenFlow events here.
        core.openflow.addListeners(self)
        # Emit startup marker for troubleshooting and proof-of-run.
        self._write_log("INFO", "POX controller started")

    @staticmethod
    def _now():
        """Return local timestamp string used in all persisted log entries."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write_log(self, level, message):
        """Write a formatted line to POX logger and append it to log file."""
        line = f"{self._now()} [{level}] {message}"
        log.info(line)
        with open(self.log_path, "a", encoding="utf-8") as logfile:
            logfile.write(line + "\n")

    @staticmethod
    def _is_port_up(port_desc):
        """Infer whether a port should be considered UP.

        In OpenFlow 1.0, a port is effectively down if either:
        - The admin/config flag marks it down (`OFPPC_PORT_DOWN`), or
        - The physical/link state reports it down (`OFPPS_LINK_DOWN`).
        """
        config_down = bool(port_desc.config & of.OFPPC_PORT_DOWN)
        link_down = bool(port_desc.state & of.OFPPS_LINK_DOWN)
        return not (config_down or link_down)

    def _display_switch_status(self, dpid):
        """Log a compact one-line summary of known ports for a switch."""
        states = self.port_state.get(dpid, {})
        if not states:
            return

        parts = []
        for port_no, is_up in sorted(states.items()):
            parts.append(f"{port_no}:{'UP' if is_up else 'DOWN'}")
        log.info("STATUS %s => %s", dpid, ", ".join(parts))

    def _handle_ConnectionUp(self, event):
        """Handle new switch connection and snapshot initial port states.

        POX emits this once the OpenFlow handshake with a datapath is complete.
        The event includes a port list (`event.ofp.ports`) which is used as the
        initial baseline for each interface before incremental PortStatus events
        begin to arrive.
        """
        dpid = dpid_to_str(event.dpid)
        # Keep reference to connection in case future features need push actions.
        self.switches[event.dpid] = event.connection
        self.port_state.setdefault(dpid, {})

        # Prime state map from the switch's port description list.
        for port_desc in event.ofp.ports:
            self.port_state[dpid][port_desc.port_no] = self._is_port_up(port_desc)

        self._write_log("INFO", f"Switch connected: {dpid}")
        self._display_switch_status(dpid)

    def _handle_ConnectionDown(self, event):
        """Handle switch disconnect event and emit alert log line.

        We intentionally keep the last known port_state snapshot for historical
        visibility; only the active connection object is removed.
        """
        dpid = dpid_to_str(event.dpid)
        if event.dpid in self.switches:
            del self.switches[event.dpid]
        self._write_log("ALERT", f"Switch disconnected: {dpid}")

    def _handle_PortStatus(self, event):
        """Process ADD/DELETE/MODIFY port status notifications from a switch.

        OpenFlow sends this for interface lifecycle and state transitions.
        The handler maps wire-level reason codes into readable labels, updates
        the in-memory state table, and writes a timestamped log record.
        """
        dpid = dpid_to_str(event.dpid)
        desc = event.ofp.desc
        port_no = desc.port_no

        if event.added:
            reason = "ADD"
        elif event.deleted:
            reason = "DELETE"
        elif event.modified:
            reason = "MODIFY"
        else:
            # Defensive fallback if a vendor/implementation sends an
            # unexpected reason code outside standard OF1.0 values.
            reason = f"UNKNOWN({event.ofp.reason})"

        # Recompute current state from latest descriptor and persist in-memory
        # view so the latest status can be printed at any moment.
        is_up = self._is_port_up(desc)
        self.port_state.setdefault(dpid, {})[port_no] = is_up

        # Treat any down state as alert-worthy; up transitions are informational.
        state_label = "UP" if is_up else "DOWN"
        level = "ALERT" if not is_up else "INFO"

        self._write_log(level, f"Port change on {dpid}:{port_no} reason={reason} state={state_label}")
        self._display_switch_status(dpid)


def launch():
    """POX entrypoint called when module is loaded via `pox.py` command."""
    core.registerNew(PortStatusMonitor)
