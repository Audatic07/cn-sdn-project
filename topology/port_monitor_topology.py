#!/usr/bin/env python3
"""Mininet topology for SDN Port Status Monitoring demo.

This script creates a simple star topology used to validate POX port-status
events:
- One Open vSwitch bridge (`s1`) speaking OpenFlow 1.0.
- Three hosts (`h1`, `h2`, `h3`) connected to that switch.

The topology is intentionally small and deterministic so link up/down actions
issued from the Mininet CLI can be correlated directly with controller logs.
"""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.topo import Topo


class PortMonitorTopo(Topo):
    """Custom Mininet topology with one switch and three edge hosts."""

    def build(self):
        # Force OpenFlow 1.0 so protocol behavior aligns with the POX module
        # imported as `pox.openflow.libopenflow_01` in the controller.
        switch = self.addSwitch("s1", protocols="OpenFlow10")

        # Fixed host IP/MAC addressing keeps experiments repeatable and avoids
        # ambiguity when reading packet captures or controller event logs.
        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")

        # Uniform link characteristics simplify debugging by ensuring observed
        # behavior differences are due to port transitions, not link asymmetry.
        self.addLink(h1, switch, cls=TCLink, bw=10, delay="5ms")
        self.addLink(h2, switch, cls=TCLink, bw=10, delay="5ms")
        self.addLink(h3, switch, cls=TCLink, bw=10, delay="5ms")


def run():
    """Instantiate topology, connect to remote POX controller, and open CLI.

    Lifecycle:
    1. Build Mininet graph from PortMonitorTopo.
    2. Attach a remote controller expected on localhost:6653.
    3. Start network and print commands that trigger port state transitions.
    4. Hand control to interactive CLI until user exits.
    5. Stop and clean up Mininet network state.
    """

    # Create topology object first so it can be passed to Mininet constructor.
    topo = PortMonitorTopo()

    # `controller=None` prevents Mininet from auto-spawning a local controller.
    # We explicitly add a RemoteController below to connect to the POX process.
    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSKernelSwitch,
        autoSetMacs=False,
        autoStaticArp=False,
    )

    # Match default OpenFlow TCP endpoint typically used by controller scripts.
    net.addController(RemoteController("c0", ip="127.0.0.1", port=6653))

    # Start all network elements and print quick commands to exercise DOWN/UP
    # events on different host-facing switch ports.
    net.start()
    info("\n*** Network started. Useful CLI commands:\n")
    info("mininet> links\n")
    info("mininet> link s1 h2 down   # trigger DOWN event\n")
    info("mininet> link s1 h2 up     # trigger UP event\n")
    info("mininet> link s1 h3 down   # trigger another DOWN event\n")
    info("mininet> link s1 h3 up     # trigger another UP event\n\n")

    # Keep the topology running for manual experiments until user exits CLI.
    CLI(net)

    # Ensure links, interfaces, and processes are cleanly torn down.
    net.stop()


if __name__ == "__main__":
    # Mininet's `info()` messages are hidden unless log level is set to info.
    setLogLevel("info")
    run()
