# Port map

This chapter lists every TCP and UDP port a Seestar client or a stand-in device deals with: who
serves it, what it carries, which catalog service documents it, the order in which a client
opens them, and how the remote tunnel maps them. It sits under all application chapters and
beside [LAN discovery](lan-discovery.md) (how the address is found) and the remote transport
([Kalay/IOTC session](iotc/index.md), [P2P tunnel](p2p-tunnel/index.md)). The control-stream
handshake is in [session-handshake.md](../control/session-handshake.md).

## Conventions

MUST, SHOULD and MAY are used as in RFC 2119 and RFC 8174. Labels as in `CONVENTIONS.md`:
**READ** (static analysis of firmware 9.31 or Android app 3.3.2), **OBSERVED** (date given),
**INFERRED**, **unresolved**. The imager runs as a main process and, for the
wide/auxiliary camera, a second process (process type 2). READ.

## Device ports

### Ports a client uses

| Port | Proto | Served by | Carries | Catalog service | Label |
|---:|---|---|---|---|---|
| 4720 | UDP | imager (main) | Seestar scan `scan_iscope`, JSON line in, JSON datagram out | [discovery](../../docs/discovery/methods/scan_iscope.md) | READ |
| 4700 | TCP | imager (main) | Main control: JSON requests, replies and events; requests end in CR or LF, output in CR LF | control | READ |
| 4800 | TCP | imager (main) | Main (telescope) camera image socket; binary/text replies | files | READ |
| 4804 | TCP | imager (process 2) | Wide camera image socket | files | READ |
| 4801 | TCP | imager (main) | Album/file socket: file lists, thumbnails, downloads | files | READ |
| 80 | TCP | HTTP file server (separate process) | HTTP GET from the image store; POST and PUT uploads on `/ai_process`; no authorization (R2) | files | READ |
| 4554 | TCP | imager (main), while streaming | RTSP, `rtsp://<host>:4554/stream` (main camera) | video | READ |
| 4555 | TCP | auxiliary imager, S30 Plus-class models only, while streaming | RTSP, `rtsp://<host>:4555/stream` (wide camera) | video | READ |
| 4350 | TCP | updater | Firmware-update JSON commands and events | updater | READ |
| 4361 | TCP | updater | Firmware-update binary upload | updater | READ |

### Ports a client does not normally use

| Port | Proto | Served by | Carries | Catalog service | Label |
|---:|---|---|---|---|---|
| 4400 | TCP | guider | Guider JSON command/event server. The imager connects to it and relays unknown 4700 methods to it (10000 ms wait) and forwards its events to 4700 | guider | READ |
| 4500 | TCP | guider | Guider image server; fixed binary frames ([Guider image server (4500)](#guider-image-server-4500)) | none | READ |
| 4030 | TCP | guider | Raw serial bridge (ser2net); a client is accepted only while its IP has a verified 4040 client (R3a) | serial-bridge | READ |
| 4701 | TCP | imager | Secondary JSON server with its own client map; not a copy of 4700's event broadcast. The guider sends local requests (for example `play_sound`) to it. Serves the same method table as 4700 ([session handshake R1a](../control/session-handshake.md)) | control (same table as 4700) | READ |
| 4702 | TCP | imager (process 2) | Wide/auxiliary JSON event/RPC server. The main imager reads its events and forwards them to 4700 | none | READ |
| 4040 | TCP | guider | Serial-bridge control server (`set_settings`, `disconnect`); in the client-auth port set. The only 4040 listener in the firmware | serial-bridge | READ |
| 139 | TCP | accepts connections; service not characterized (NetBIOS session service INFERRED, [smb.md R10](../media/smb.md#reachability)) | No app use; not in the remote map | none | OBSERVED 2026-10-16 |
| 445 | TCP | Samba daemon | SMB share of the image store ([smb.md](../media/smb.md)). No app use; not in the remote map | none | READ (start), OBSERVED 2026-10-16 |
| 32761 | UDP | Kalay SDK inside the imager | Kalay LAN search, opcodes 0601 to 0604 | none ([lan-discovery/kalay-search.md: Kalay LAN search: opcodes 0601 to 0604](lan-discovery/kalay-search.md#kalay-lan-search-opcodes-0601-to-0604)) | READ |

R1. A client SHOULD reach the guider through 4700 (relay) rather than connecting to 4400. The
app does not dial 4400, 4500, 4030, 4040, 4701 or 4702. READ (app inventory). Every listener
inspected binds all interfaces, not loopback: the imager JSON and image servers (4700, 4701, 4702,
4800, 4801, 4804), the guider servers (4400, 4500, 4040, 4030), UDP 4720 and HTTP 80. Access is controlled by
verification (R3, R3a), not by the bound address. READ.

R2. 4800, 4804 and 4801 share the imager's common socket worker but are not in the
client-auth port set; 4350, 4361 and 80 use separate serving paths. READ. The HTTP server on 80
authorizes nothing: no header, token, serial or credential is checked. GET serves files from the
image store; POST and PUT on `/ai_process` accept uploads. The only input check rejects path
traversal (403). Any client that reaches the port can read and upload. READ. Routes and
resolution are in [files-and-album.md: HTTP 80](../media/files-and-album.md#http-80).

R3. The client-auth port set is 4040, 4400 and 4700 to 4702: on these, an unverified external
client's ordinary requests are silently consumed. READ. See the
[session handshake](../control/session-handshake.md).

R3a. 4030 is gated by 4040. The bridge accepts a 4030 client only while a client from the same
source IP is verified on 4040, or while factory mode is on; otherwise it closes the socket at
once. When that IP no longer has a verified 4040 client, the bridge closes its 4030 connections.
READ. See [serial-bridge.md](../guider/serial-bridge.md).

R3c. Firmware 9.75, 64-bit builds: whether those ports enforce verification depends on the device
configuration switch `secure_communication` (shipped enabled); the 32-bit builds always enforce
it, as firmware 9.31 did on all builds. The port set itself is unchanged, the image/file sockets
(4800, 4801, 4804, 4500) are still outside it, and the streams stay plaintext JSON: the
secure-communication layer encrypts selected Wi-Fi password fields only. READ. See
[secure communication](../control/secure-communication.md). Firmware 9.75, both file-server builds: HTTP port 80 keeps the firmware 9.31 routes and checks no client authorization on those serving paths. READ (routes and handlers), INFERRED (no authorization anywhere in the initialized serving graph). The JSON-port verification layer does not protect HTTP access.

R3d. Firmware 9.75 listener set (READ, imager, guider, updater, file server and BLE daemon; the
64-bit imager was compared most closely): the `bind` and `listen` sites match firmware 9.31 and no
new TCP or UDP listener exists. The imager still sets up 4700, 4701, 4702, 4720, 4800, 4801 and
4804, the RTSP setup still uses 4554 and 4555, and the guider connection still uses 4400 and 4702.
The UDP 4720 discovery path is identical in structure. The BLE daemon has no `bind` or `listen`
call. The 9.75 imager contains an HTTP library with server classes, but no listener is created
from them (a client or dormant code; READ). The 32-bit builds and the guider were checked less
closely. The file server has the same listener count and symbols. Its route table and authorization were compared: R2 applies to firmware 9.75, both builds (READ for routes, INFERRED for the absence of added authorization; R3c). The 64-bit file server adds a 16-thread pool, and both builds add a local download limiter and file-read chunks of up to 32768 bytes; neither is access control. Whether the 32-bit server's threading matches is unresolved.

R3e. Firmware 9.75 updater (READ for the call sites, INFERRED for their meaning): the updater
main routine starts the control server on 4350 and the binary server on 4361, and also records
4361 as the binary port that `ota_prepare_module` reports (the second 4361 site; one site in
firmware 9.31). READ (resolved: the second site is the reported-port value, next to the one that
starts the binary server). The OTA manager's binary-channel session holds a pending receive with a
15 s timeout (code 546; [updater R12e](../updater/ota-package-handling.md#ota-package-handling)).
No new port is involved.

### Outbound device traffic

The device's Kalay SDK talks to Kalay servers: UDP 10240, and TCP on 80, 443, 21047, 8080 and
8000 in rotation (port numbers only; 80 and 443 do not imply HTTP or TLS). READ. See
[iotc/connect.md](iotc/connect.md). The device's cloud API use is in
[cloud-auth.md](../auth/cloud-auth.md).

Firmware 9.75 adds no outbound port-80 client. The updater's OTA version-information function reads
a local manifest file and has no socket or HTTP code (READ). See [updater
R12f](../updater/ota-package-handling.md#ota-package-handling). The device's cloud messaging uses
MQTT to the vendor IoT platform ([device-cloud-link.md](../auth/cloud-auth/device-cloud-link.md)).

## Framing per port family

| Port(s) | Framing | Label |
|---|---|---|
| 4700, 4701, 4702, 4400, 4040 | JSON text; a request line ends at any CR or LF byte (no CR LF pair needed); lines of 4 bytes or fewer are ignored; a `jsonrpc` member in a request is ignored; device output strips LF, keeps CR and appends CRLF | READ |
| 4720/UDP | Request line needs CR or LF; reply is one datagram with no terminator | READ |
| 4800, 4804, 4801 | JSON requests as on 4700; replies binary or text per method (see the `files` cards) | READ (requests), per-method (replies) |
| 4350 | JSON control/events with its own (legacy) idle clock | READ |
| 4361 | Binary upload; notifications appear on 4350 | READ |
| 4500 | Binary frames ([Guider image server (4500)](#guider-image-server-4500)) | READ |
| 4030 | Raw serial bytes, no framing | INFERRED |
| 4554, 4555 | RTSP; RTP over interleaved TCP or UDP `client_port`; no authentication, no idle timeout, keepalive optional and only by `OPTIONS` (see [video.md R3a, R3c, R3d](../media/video.md#rtsp-endpoints)) | READ |
| 80 | HTTP | READ (URL use) |
| 32761/UDP | Binary IOTC legacy frames | READ |

### Guider image server (4500)

R3b. 4500 does not use newline-delimited JSON for its output. Requests are JSON texts with `id`
and `method`; the request verbs are `test_connection`, `begin_streaming` and `stop_streaming`.
Every reply and every pushed image is a binary frame with an 80-byte header. In order, the header
holds: the 4-byte magic `03 c3 00 02` (the LE32 value `0x0200c303`), a big-endian 16-bit header
length (80) at offset 4, a big-endian 32-bit payload length, a payload-type byte at offset 14
(1 for a text reply) and the low byte of the request `id` at offset 15. 16 zero bytes sit at
offset 64. Image payloads carry big-endian 16-bit width, height and star position. READ. The byte at
offset 12 is always 0, the reserved byte of the image-socket header
([image-sockets.md: Reply framing](../media/image-sockets.md#reply-framing)). READ. 4500 is not in the
client-auth port set. READ. Streaming and the text error replies are in
[guider R1a](../guider/index.md#endpoints).

The header is built by a routine shared with the imager's JSON servers. The imager image sockets
4800, 4801 and 4804 use the same magic and 80-byte header (READ, [image-sockets.md: Reply framing](../media/image-sockets.md#reply-framing)), and the
4500 server uses the same 80-byte base header (READ,
[image-sockets.md R10a](../media/image-sockets.md#reply-framing)). One value differs: 4500 puts
1 at offset 14 for a text reply, while the imager puts dataType 0 there for an ok text reply and
1 only for an error text. READ (both). See [guider R1a](../guider/index.md#endpoints).

## Client connection order and readiness

Basis: static analysis of app 3.3.2 (connection managers) and firmware 9.31 (socket worker).

```text
client                                                    device
  |-- UDP 4720 scan_iscope (LAN tab) ----------------------->|   optional for a known address
  |<- reply from device address -----------------------------|
  |== TCP 4700 connect ======================================>|
  |   get_verify_str / verify_client                          |   session-handshake.md; 9.75: key envelope
  |   initialization writes and reads                         |
  |   (device sends a Version greeting on arrival)            |
  |== TCP 4800, then 4804 (only once 4700 is connected) =====>|
  |== TCP 4801 (on service readiness and album work) ========>|
  |-- HTTP 80, RTSP 4554/4555 when the feature needs them --->|
  |== TCP 4350, then 4361, only for a firmware update =======>|
```

R4. The app opens 4700 first. Image sockets 4800 and 4804 are requested right after, but the
app defers them while 4700 is not connected and retries every 3000 ms. This is a code
dependency, not a guaranteed order of SYN packets. READ.

R5. 4801 opens when the device service reports ready and for album work. HTTP, RTSP and the
update ports are opened by features. There is no single mandatory order for all ports. READ.

R6. A client MUST open 4700 and complete the handshake before relying on the other sockets.
INFERRED from R4 and from the 4700 handshake gating control.

R7. Heartbeats: the app sends `test_connection` on 4700 when more than 2000 ms passed since the
last one; the image and file sockets send `{"method": "test_connection", "id": 1}` CRLF every
3000 ms; the updater socket has a 3000 ms heartbeat. READ. The device closes an ordinary
external client on 4700, 4800, 4804 or 4801 after more than 15000 ms without received bytes
(checks can add delay). READ. A client MUST send something on every open socket at least every
15 s and SHOULD use the app's intervals (INFERRED from the idle rule).

R8. The app discards callbacks from a socket whose configured host differs from the current
control host. It does not compare the peer address with the scanned address. A client SHOULD
open all sockets to the same host as 4700. READ.

R9. Remote readiness: after the tunnel and port maps are up, the app waits up to 30000 ms for
device state on 4700 before declaring the connect failed. Tunnel success alone is not
readiness. READ.

R10. A stand-in or relay MUST use one upstream TCP stream per client stream and preserve byte
order, events, EOF and shutdown. It MUST keep a 4700 stream's verification and later requests on
the same upstream connection, because the challenge is per connection. INFERRED.

## Remote tunnel port mapping

In `REMOTE` mode the app opens two P2P tunnel sessions and maps local loopback ports to device
ports. READ. All application sockets then dial `<loopback>` on the local port.

| Group (tunnel session) | App label | Local TCP | Device TCP |
|---|---|---:|---:|
| Primary (first) | SOCKET | 4700 | 4700 |
| Primary (first) | FW_SOCKET | 4350 | 4350 |
| Secondary (second) | HTTP | 8080 | 80 |
| Secondary (second) | RTMP | 4554 | 4554 |
| Secondary (second) | RTMP_WIDE | 4555 | 4555 |
| Secondary (second) | FILE | 4801 | 4801 |
| Secondary (second) | PIC | 4800 | 4800 |
| Secondary (second) | PIC_WIDE | 4804 | 4804 |
| Secondary (second) | FW_UPLOAD | 4361 | 4361 |

The `RTMP` and `RTMP_WIDE` labels are the app's own names for the 4554 and 4555 entries. READ. The app dials these ports with the scheme `rtsp://` (`rtsp://<host>:4554/stream` and `rtsp://<host>:4555/stream`). READ. The app uses these fixed ports and ignores the `port` member of the `RTSP` event ([video.md R7b](../media/video.md#rtsp-event)). READ (app 3.3.2). That the device speaks the RTMP protocol on these or any other ports is not established; see [video.md](../media/video.md#rtsp-endpoints).

R11. Sequence: connect the first tunnel; if it succeeds, connect the second; require both;
map the primary group on the first session, then the secondary group on the second; stop and
release everything on any failure. READ. Details in [p2p-tunnel/seestar-profile.md](p2p-tunnel/seestar-profile.md).

R12. The app builds HTTP URLs as `http://<loopback>:8080/...` in `REMOTE` mode and as
`http://<device>/...` (port 80) on the LAN. READ.

R13. These are nine mappings, not nine connections opened at once. 445, 4720, 4400, 4500, 4030,
4040, 4701 and 4702 are not mapped. READ. A minimal remote client MAY map only 4700. INFERRED.

R13a. The device's tunnel server accepts a mapping to any remote port
([p2p-tunnel/framing.md R20](p2p-tunnel/framing.md)). READ. A mapping to 445, outside the app's
nine, was accepted and forwarded. OBSERVED 2026-10-16. Unmapped ports are therefore not
protected by the tunnel profile. INFERRED.

R14. When the IOTC path is LAN, mapped streams may bypass the tunnel over direct TCP to the same
device ports ([lan-discovery/kalay-search.md: Optional LAN-direct socket bypass](lan-discovery/kalay-search.md#optional-lan-direct-socket-bypass)). Such
streams reach the device as external connections. INFERRED.

R15. The device classes as internal only connections whose source equals the address it
resolves for `localhost` (the loopback address). READ. For such a connection the connection
attribute for "external" is cleared, the "is local" test is true and the "is verified" test returns
true without a signature; otherwise verification needs the connection's verified byte to be set.
READ (firmware 9.31 and 9.75, 64-bit; the same logic in both). Tunnel-delivered streams arrive from
the tunnel daemon on loopback and are therefore treated as verified. INFERRED, OBSERVED 2026-10-12
(4700 requests answered over the tunnel without `verify_client`; firmware 9.31). That chain depends
on the app requesting the loopback address as the tunnel destination (INFERRED); a client that asks the tunnel for the
device's LAN address would arrive from that address and would not match (INFERRED, unchecked).
The tunnel server's port-verification callback allows every port (READ, firmware 9.75, 64-bit). LAN and LAN-direct streams are external.
READ (LAN), INFERRED (LAN-direct).

R15a. Firmware 9.75 (secure communication over the tunnel). The new field-encryption layer
protects selected fields on the accepted JSON socket only. It does not replace IOTC, RDT or MQTT
transport encryption, and no cloud command dispatch was found that calls its encode or decode
routines (READ, 64-bit imager). Whether a tunnel stream is exempt from ordinary request
authorization still depends on it being classified as internal, and the chain from the tunnel
daemon's loopback connection to that classification is INFERRED, as is its parity in the 32-bit
build. The field-session requirement is independent of that classification: a tunnel client is not
required to obtain the key envelope to send ordinary requests, but an operation that needs a crypto
session (the Wi-Fi password fields) fails without one and can only succeed if the client ran the
handshake on its own stream. A client MUST NOT assume that every tunnel client must first obtain
the envelope, and MUST NOT assume that the Wi-Fi password operations work without it.
See [secure communication](../control/secure-communication.md).

### Transport and authentication review (firmware 9.75, app 3.4.0, iOS app 3.4.0)

A later sweep compared the transport, authentication and updater statements of this specification
with firmware 9.75 (64-bit builds closely, 32-bit builds and the guider more lightly) and with the
iOS app 3.4.0 frameworks. Static reading only; nothing was run on a device. Statements elsewhere
stay firmware 9.31 unless tagged. Summary of what changed in these areas:

| Area | Result | Where |
|---|---|---|
| Listener set | Unchanged on every process; no new port or listener. The updater uses the binary port at a second site (OTA session). READ | [ports.md R3d, R3e](ports.md) |
| OTA version information | New function reading the local manifest file (no port-80 query). READ | [OTA package handling R12f](../updater/ota-package-handling.md#ota-package-handling); [outbound traffic](#outbound-device-traffic) |
| Kalay SDK | Same version word and revision strings; logging stripped, handlers inlined (named handlers 24 to 15 is compiler inlining and folding); opcode set identical, no wire message added or removed. READ | [iotc/index.md: Firmware 9.75 build comparison](iotc/index.md#firmware-975-build-comparison) |
| RDT | Compared parts unchanged; reliability constants not verified for 9.75 | [rdt.md: App / firmware comparison](rdt.md#app--firmware-comparison) |
| LAN discovery | UDP 4720 handler unchanged in structure; helpers and reply builders not compared | [lan-discovery.md](lan-discovery.md) |
| SDK licence | Firmware-embedded default licence with optional `changSdkLicenseKey` override; `sdkLicenseKey` no longer read. READ | [sdk-licence.md R46a](../auth/cloud-auth/sdk-licence.md) |
| Busy gate | Different-`srcId` gate 70 s (9.31) to 65 s (9.75). READ | [http-api.md: `srcId` stability and the busy window](../auth/cloud-auth/http-api.md#srcid-stability-and-the-busy-window) |
| Tunnel server start | Retry once on -30007. READ | [sdk-licence.md: Device-side SDK start](../auth/cloud-auth/sdk-licence.md#device-side-sdk-start) |
| Send-rate and relay mode | `p2p_init` optional `rate` (KiB/s, shifted left by 10) and `rateLimit`; relay mode cleared on disconnect. READ | [sdk-licence.md R46b, R46c](../auth/cloud-auth/sdk-licence.md) |
| P2P status upload | Firmware 9.75 (64-bit build): the attribute report carries `conId` and `p2pStatus` strings, `natMode` only when nonempty, and an integer `code` only when present. State 3 maps to `occupied`; it is not code 3. The failure path adds the P2P start return code with `initFailed`. Identical reports are suppressed. READ. Backend acceptance is not established | [cloud-auth.md: Open questions](../auth/cloud-auth.md#open-questions) |
| Embedded keys | Identical; a third device-side public key is used by client authentication (location and role only) | [embedded-constants.md: Device-side client-authentication public key (location only)](../auth/cloud-auth/embedded-constants.md#device-side-client-authentication-public-key-location-only) |
| Tunnel wire protocol | Unchanged. READ | [seestar-profile.md R69a](p2p-tunnel/seestar-profile.md) |
| Secure communication over the tunnel | Tunnel clients are not required to obtain the key envelope; the internal-classification chain is INFERRED | [ports.md R15a](ports.md), [seestar-profile.md R81a](p2p-tunnel/seestar-profile.md) |
| iOS 3.4.0 | SDK 4.3.6 build 3, login version `0x04030603`; new endpoints `device-p2p/retrieve` and `my-device/remote-unbind` (request/response shapes READ); plain transform phrase. iOS app 3.4.0 configures two tunnel mapping groups, dispatches their connection attempts asynchronously and signals success after both return nonnegative results. Its device-details removal action invokes remote-unbind; its traced ordinary disconnect uses the stop operation after status/identifier checks. A main caller of retrieve remains unresolved. Main Apple registration uses platform=apple and authType=email. Ticket parsing, application headers and the separate main/framework signing builders are described in [endpoints.md R31a](../auth/account-login/endpoints.md). READ for these client paths; backend effects and Android app 3.3.2 parity remain unresolved. | [endpoints.md R31a](../auth/account-login/endpoints.md), [http-api.md: Optional remote-feature catalogue](../auth/cloud-auth/http-api.md#optional-remote-feature-catalogue) |
| Updater | `ota_abort` result 0 (524 while upgrading); `ota_get_session` member set; `OtaUpdate` is a broadcast | [index.md R11 to R11b](../updater/index.md) |

Still unresolved after the sweep: file-server route and authorization parity ([HTTP download limiting](../media/files-and-album.md#http-download-limiting-firmware-975)), RDT
reliability constants (roles), the done-marker consumer, the helper directory of the reboot call, the wire
effect of the status upload, and the iOS request shapes. The P2P monitor and occupy timers (300 s tick,
12 and 24 ticks, 65 s) and the 2 s reboot delay are resolved (firmware 9.75, READ), see
[device-cloud-link.md](../auth/cloud-auth/device-cloud-link.md) and [OTA package handling R12c](../updater/ota-package-handling.md#ota-package-handling). They are listed in the open
questions of the chapters named above and in [index.md: Open questions](../updater/index.md#open-questions).

## Open questions

- Firmware 9.75: the file-server route table and authorization match R2 on both builds (R3c, R3d); whether the 32-bit server's threading matches the 64-bit 16-thread pool is unresolved.
- Firmware 9.75: the RDT reliability constants are present unchanged in both versions but their
  roles were not traced (see [rdt.md: App / firmware comparison](rdt.md#app--firmware-comparison)). unresolved.
- Firmware 9.75: the app requesting a loopback destination for tunnel-forwarded connections, and the
  32-bit parity of the classification chain (R15, R15a). INFERRED.

- Whether any feature on iOS uses 445 or other extra ports. unresolved.
- Idle rules on 80: library defaults, see [files-and-album.md R19](../media/files-and-album.md#http-80); the library version is unresolved.
