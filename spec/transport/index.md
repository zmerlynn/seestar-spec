# Transport

Everything below the JSON layer: how a client finds the telescope and reaches its ports, either
directly on the LAN or through the Kalay cloud tunnel. Read the port map first.

## Contents

- [Port map](ports.md): every device listener and which layer owns it.
- [LAN discovery and device selection](lan-discovery.md): finding a device on the local network.
- [Kalay/IOTC session](kalay-iotc-session.md): the cloud session a remote client opens, with the
  wire-level [IOTC detail](iotc/index.md).
- [RDT reliable data channel](rdt.md): ordered, acknowledged streams over an IOTC session.
- [P2P tunnel](p2p-tunnel.md): TCP port forwarding over RDT, with the
  [tunnel detail](p2p-tunnel/index.md).
- [BLE transport and activation boundary](ble.md): local Bluetooth provisioning, separate from
  the remote-access stack above.
