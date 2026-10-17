# BLE transport and activation boundary

BLE activation requests and replies are documented in [Maintenance: Activation: pi_encrypt](../control/maintenance.md#activation-pi_encrypt), including the app 3.3.2 `ble_connect` reply and the `send_to_air_reply` frame carrying activation parameters. READ (app 3.3.2).

App names: the app's “Online Activation” screen is the activation described here. Names are the
English strings of iOS app 3.4.0; links are READ (app call sites) unless marked.

This chapter collects the BLE comparison notes; it does not specify a complete BLE framing format or command catalogue. See maintenance for the documented activation exchange.

## Version comparison

R16. The BLE daemon is byte-identical between firmware 9.31 and 9.75 in both builds (READ), so there
is no BLE command or member change. The BLE daemon in both builds always reads the `serc` value from
the 2.4 GHz access-point configuration file, whichever band the access point is linked to, whereas
the LAN discovery scan reads the linked band; see [LAN discovery, app
scan](lan-discovery/app-scan.md).


## Open questions

- Complete BLE framing and transport scope are not specified here.
