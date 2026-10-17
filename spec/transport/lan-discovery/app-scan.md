# Seestar UDP 4720 scan and device selection

Part of the [LAN discovery chapter](../lan-discovery.md). This file specifies the app-level UDP
4720 scan, the device-side responder, how the app picks a LAN or remote target, and a summary of
the control connection that follows. Labels: [lan-discovery.md: Conventions](../lan-discovery.md#conventions).

## App-level discovery: UDP 4720

Basis: static analysis of app 3.3.2 (UDP scanner, LAN tab) and firmware 9.31 (`scan_iscope`
handler, UDP thread).

### Request

The client sends one JSON line in one UDP datagram to the Wi-Fi subnet's directed broadcast
address, port 4720. READ.

```text
client:<ephemeral>  ->  <subnet-broadcast>:4720/UDP
{"id":N,"method":"scan_iscope","params":""}<CR><LF>
```

ABNF (RFC 5234), as the app sends it:

```abnf
scan-request = "{" DQUOTE "id" DQUOTE ":" id-value
               "," DQUOTE "method" DQUOTE ":" DQUOTE "scan_iscope" DQUOTE
               "," DQUOTE "params" DQUOTE ":" DQUOTE DQUOTE "}" CRLF
id-value     = 1*5DIGIT                     ; 1..32767
```

R1. The request MUST end with a CR or LF byte. The device dispatches only on a physical line
delimiter; a datagram without one gets no reply. READ.

R2. A client SHOULD send the whole request, delimiter included, in one datagram and SHOULD keep
it short. The device's line reader persists across datagrams and senders ([Listener and framing](#listener-and-framing)). READ.

R3. Member order is not significant. There is no `jsonrpc` member in the app's request. The
`params` value is not read by the handler. READ.

The device's request dispatcher looks only at the root members `id`, `method` and `params`. It
needs `id` (any value; absent gives code 200) and a string `method` (absent or not a string gives
code 100). `params` is optional: when absent the handler is called with no params, and the
`scan_iscope` handler does not read params in any case. Any other root member is skipped. READ
(firmware 9.31).

The iOS app's request differs: root members `id` (integer), `method` (`scan_iscope`), `name` and
`ip` (strings), no `params` and no `jsonrpc`, ending in CRLF. OBSERVED (2026-10-12, iOS app
through a LAN proxy; app version not recorded). The replies in that observation were produced by
the proxy, so no native reply to this form has been observed. The device ignores `name` and `ip`
and does not require `params` (READ, dispatcher above), so it answers this form exactly as it
answers the Android form. INFERRED from READ code. The Android app 3.3.2 sends only the form
shown above, with `params` set to the empty string and no `name` or `ip`. READ.

The scan is a LAN operation only. Port 4720 is not among the tunnel port mappings
([ports.md R13](../ports.md#remote-tunnel-port-mapping)), and the Android app sends the scan only
from its LAN tab over Wi-Fi (R7). READ. Whether iOS scans in remote mode is unresolved.

R4. The app's `id` comes from a signed 16-bit counter that wraps back to 1 at 32767. A client
MAY use any id. READ.

R5. The app sends from one unbound UDP socket (ephemeral source port, broadcast enabled) and
receives replies on that same socket. A client MUST listen on the source port it sent from;
replies do not go to port 4720 on the client. READ.

### Choosing the broadcast address

The app searches its Wi-Fi networks (bound network, then active network, then the rest), takes
a site-local IPv4 address, and sets the host bits from the prefix length to form the directed
broadcast. With no usable Wi-Fi IPv4 it does not send and waits. It does not use
the limited (all-ones) broadcast address, mDNS, SSDP or multicast, and does not scan non-Wi-Fi interfaces. READ.

R6. A client MAY also unicast the request to a known device address. The device processes
unicast and broadcast alike (INFERRED from the listener having no destination check, READ).
Delivery across routers, AP isolation or station mode is unresolved.

### Timers

| Timer | Value | Label |
|---|---|---|
| Sends per scan run | at most 10 successful sends, stopping early once connected | READ |
| Interval between sends | 2000 ms | READ |
| Retry after socket creation failure | 500 ms | READ |
| Retry when no broadcast address | 2000 ms | READ |
| Retry after a send exception | 5000 ms | READ |
| Receive buffer | 4096 bytes | READ |
| Result windows | overlapping 10000 ms windows started every 3000 ms | READ |
| LAN tab poll | 500 ms | READ |
| LAN tab "nothing found" | 20000 ms | READ |
| Connect page UI timeout after a click | 15000 ms (not a socket connect timeout) | READ |

R7. The LAN tab scans only while visible, with Wi-Fi on and permissions granted, and stops on
pause or when hidden. READ. Clients need not copy these timers. A client SHOULD repeat the
request a few times, since UDP is unreliable (INFERRED).

### Accepting a reply

The app parses each datagram as JSON with platform-default text decoding. READ.

R8. The app accepts a reply only if `result` is present and `result.sn` is a non-empty string.
It does not check `method`, `id`, `code`, `jsonrpc` or the source port. An absent `sn` can
crash the receive thread (no null check). READ.

R9. The device address is the datagram's **source IP address**. No address member exists in the
reply. The display name is `result.ssid`. READ.

R10. If the source address ends in `.1` (typically the device acting as access point,
INFERRED), the app also reads `is_verified`. `false` raises the app's "device not activated" prompt; it does not
suppress the device from the list. A missing value can crash the thread. READ.

R11. The app's list keys entries by non-blank `sn`, falling back to the IP. The first record per
key in a snapshot wins. Two hosts advertising the same `sn` therefore compete for one row.
READ (key logic), INFERRED (consequence).

### Reply fields

Members of `result`. Types are the app's DTO types where the firmware type is not established.

| Member | Type | Meaning | Label |
|---|---|---|---|
| `sn` | string | Device serial (hardware serial when available). Required by the app | READ |
| `ssid` | string | Display name; the device's AP name | READ |
| `product_model` | string | Model; drives the app's model/sub-model choice | READ |
| `custom_model` | string, optional | Sub-model refinement | READ |
| `is_verified` | boolean | Hardware activation state. Not client authentication | READ |
| `tcp_client_num` | integer | Distinct external client IPs retained by the 4700 server, unverified sockets included | READ |
| `connect_lock` | boolean | LAN lock enabled | READ |
| `password` | string | MD5 digest of the lock password, as hex text | READ |
| `serc` | string | The access point's key-management (security) mode: the raw text of the `wpa_key_mgmt` setting in the hostapd configuration of the band the AP is currently linked to (2.4 GHz or 5 GHz). It is the text after the first `=` of every line containing that word, joined by single spaces, and empty when there is none. Not the pre-shared key. No shipped script or binary writes `wpa_key_mgmt` (the firmware only changes the AP's SSID, passphrase, channel and channel selection), so the value is whatever the device's base system image put there; that image is not in the update package, so the value set is unresolved (hostapd syntax suggests tokens such as `WPA-PSK`). Same in the 32-bit build. The Android app stores it but never reads it | READ (source, format, no firmware writer, both builds; app 3.3.2 ignores it); unresolved (value set) |
| `bssid` | string, optional | Advertised by firmware | READ |
| `can_star_mode_sel_cam` | boolean | Capability flag | READ |
| `model`, `pwd` | string | In the app DTO only; legacy. Not emitted by the 9.31 builder | READ |

No IP, Kalay UID or firmware version is in the reply. READ.

R12. `tcp_client_num`: the app refuses a LAN click when the value is 8 or more; absent means 0.
The count is per distinct source IP, so several sockets from one IP count once; connections
the device classes as internal count zero. READ. See the
[session handshake](../../control/session-handshake.md) for the capacity limit itself.

R13. `connect_lock`: when true, the app asks the user for a six-character password, computes
its MD5 and compares it with `password` locally. Nothing is sent to the device in that step;
it is a UI gate, not network authentication. READ. A client SHOULD treat `password` as a
secret-equivalent value and MUST NOT log it.

### Example

Synthetic values. The device omits optional members it cannot fill; the exact serialized bytes
are unresolved.

```text
-> {"id":7,"method":"scan_iscope","params":""}\r\n
<- {"jsonrpc":"2.0","Timestamp":"1234.123456789","method":"scan_iscope",
    "result":{"sn":"EXAMPLESN01","ssid":"S50_EXAMPLE","product_model":"Seestar S50",
    "is_verified":true,"tcp_client_num":1,"connect_lock":false,"password":"<md5-hex>",
    "can_star_mode_sel_cam":false},"code":0,"id":7}
```

(Line-wrapped for display; the device sends one line with no line terminator, [Reply](#reply).)

## Device-side responder

Basis: static analysis of firmware 9.31, UDP thread, send helper, builder
 (64-bit); 32-bit builder.

### Listener and framing

R14. The imager binds one UDP socket to INADDR_ANY:4720. It has no destination-address check, so
broadcast and unicast requests are both processed (INFERRED from READ code). READ.

R15. Input framing: READ.

- A line ends at any CR or LF byte. Datagram boundaries are **not** line boundaries.
- Lines of four bytes or fewer are ignored.
- Several complete lines in one datagram are each processed.
- One line reader is shared by all senders and persists across datagrams. The reply goes to the
  source address of the **latest** datagram. INFERRED: an incomplete line can be completed by
  another sender's datagram and the reply then goes to that sender. Clients avoid this by
  following R1 and R2.

R16. Dispatch is by exact, case-sensitive `method` equal to `scan_iscope`, on a parsed object or
batch. Unknown methods get no reply: code 103 replies are suppressed, also for batch elements;
an all-unknown or empty batch is silent. Other dispatcher errors (for example no `id`, code 200)
can be returned. READ.

### Reply

R17. The reply uses the common reply envelope: `jsonrpc`, `Timestamp`, `method`, `result`,
`code`, `id`. READ. See the catalog card for the schema.

R18. The device removes LF bytes from the serialized reply, keeps CR bytes, and appends **no**
CRLF or NUL. One reply is one datagram. A client MUST parse a datagram whole and MUST NOT wait
for a delimiter. READ.

R19. The reply is unicast from the listening socket to the request's source address and source
port. It is never broadcast. The reply source address is the OS's choice; no per-interface
selection is done. READ.

R20. The builder reads hardware, AP, lock and client-count state. It does not query the firmware
version or the Kalay UID. READ.

R20a. Answering a scan has no persistent side effect. The builder reads device identity, AP
state, lock settings and licence files, and starts read-only helper processes (a boot-environment
read on every request, and an interface query once per process). It writes no setting and changes
no device state; its only other effects are log lines and a thread-local error code. READ.

### Access-point mode

R21. In AP mode the device's AP restart routine assigns a fixed private IPv4 address (the `.1`
host of a `10.x` network) to the AP interface and restarts hostapd. This is the address set on
that restart path; it is not proven for every boot or interface. READ.

R22. In the app's nearby/AP (`LOCAL`) mode the app prefers the discovery record whose source IP
equals the current Wi-Fi gateway ([Address entry, saved devices and LAN versus remote](#address-entry-saved-devices-and-lan-versus-remote)). A client joined to the device's AP SHOULD use the
gateway address, confirmed by a scan reply. INFERRED.

### Stand-in responders

These rules are for a host that answers scans on behalf of a real device (for example a relay).
All INFERRED from the app receive rules above.

R23. A stand-in MUST answer from an address the client can reach, since the client dials the
reply's source address. Placing an address in the JSON has no effect (R9).

R24. A stand-in SHOULD forward the real device's `result` unchanged, so that `sn`, model,
activation, lock and client count stay true. It MUST unicast to each request's source port.

R25. If the real device is also visible on the same broadcast domain, the client sees two records
with one `sn` (R11). A stand-in deployment SHOULD keep the real device's scan replies from
reaching the client.

The minimum the Android receiver needs is `result.sn` non-empty plus `ssid`; later UI and other
platforms may need more. This is not a recommendation to replace real values.

## Address entry, saved devices and LAN versus remote

Basis: static analysis of app 3.3.2, connection-mode enum and target resolver.

The app has three connection modes. READ.

| Mode (Android enum value) | How the target address is chosen | Label |
|---|---|---|
| `LOCAL` (0) | Nearby/AP flow. Requires a current scan list. Prefer the record whose IP equals the Wi-Fi gateway; else match the saved target `sn` with `tcp_client_num` < 8. A gateway match adopts that record's `sn` | READ |
| `LAN` (2) | The clicked record's source IP and `sn`. Used verbatim with no re-validation. Up to 3 retries to the same address; 1000 ms after a failure, 500 ms after a disconnect | READ |
| `REMOTE` (1) | After the cloud step and the tunnel port maps are up, every application socket dials loopback (`<loopback>`) on the mapped local ports. The selected remote `sn` is kept | READ |

R26. The app has no manual IP or hostname entry and no saved-IP or deep-link path to a connect
target was found. The LAN dialog offers scan results and the lock password only. This is a
bounded negative result for Android, not proof of absence. READ. Whether iOS allows address
entry is unresolved.

R27. A client that is not bound by the app's UI MAY connect to a configured address directly.
The device does not require a prior scan, nor that the connecting IP match a scanning IP.
READ (no such check in the device accept path).

R28. Mode selection is a user flow, not automatic routing. A device seen on the LAN does not
switch an already selected `REMOTE` session to `LAN`, and answering a scan does not redirect a
`REMOTE` session. A `REMOTE` session keeps loopback targets even when the Kalay SDK picks a LAN
path underneath ([kalay-search.md: Optional LAN-direct socket bypass](kalay-search.md#optional-lan-direct-socket-bypass)). READ.

R29. `REMOTE` requires the cloud preparation step (device UID, SDK licence and tunnel
credentials; see [cloud authorization](../../auth/cloud-auth.md)). `LAN` does not use it. A
working LAN path does not remove that prerequisite from a `REMOTE` connect. READ.

R30. After connecting, the app checks the device's own `sn` (see the
[session handshake](../../control/session-handshake.md)): `REMOTE` requires it to equal the
selected `sn`; `LAN` only requires it to be non-blank and then adopts it as the saved device.
READ.

## Control connection (summary)

After choosing an address the client opens TCP 4700 and sends newline-terminated JSON
requests. On the LAN this connection is plain TCP with no TLS. Before the device answers
ordinary requests from an external client (any source other than the address the device
resolves for `localhost`), the client must pass a
challenge-response check (`get_verify_str`, then `verify_client` with an RSA signature).
Connections the device classes as internal, which include the Kalay tunnel daemon's loopback
connection, are treated as verified. The client then runs initialization writes, a heartbeat
(`test_connection`) and guest/master ownership rules. All of this is specified in
[session-handshake.md](../../control/session-handshake.md). Port order and readiness are in
[ports.md](../ports.md).
