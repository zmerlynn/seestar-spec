# P2P tunnel: Seestar profile and layered example

Part of the [P2P tunnel chapter](index.md). This file says how the Seestar app and device
use the generic tunnel: session counts, the nine port mappings, readiness and reconnect, the
minimal outbound proxy, the first application bytes on port 4700, and a synthetic byte
example through every layer. The port list is also in [ports.md](../ports.md); the
application protocol on port 4700 starts in [session handshake](../../control/session-handshake.md).

Basis: static analysis of app 3.3.2 (Java/DEX and tunnel library) and firmware 9.31, with firmware
9.75 and the iOS app 3.4.0 tagged where they differ. The tunnel wire protocol is unchanged in
firmware 9.75 (READ).

## Integration

R68. App. READ:

- The app loads the tunnel library and connects with the extended connect call; its RDT
  credential callback supplies account and password from the cloud handoff (the `online-link`
  response, see [cloud authorization](../../auth/cloud-auth.md)). LOGIN carries no credentials.
- It uses port mapping, never service mapping.
- It initializes 4 tunnel sessions with LAN-direct enabled, sets the IOTC alive timeout to
  30 s, and asks for a 512000-byte buffer threshold.
- A local bind failure (-30002) is retried once after 250 ms.
- On disconnect it removes the mappings, then aborts and disconnects each session.

R69. Device. READ: the imager starts a tunnel Server for 64 sessions with LAN-direct
enabled, IOTC alive timeout 30 s, the always-allow port callback, the account/password
callback and a session callback that sets a 5120000-byte threshold (R20). No service callback
is registered in the inspected startup path.

R69a. Firmware 9.75 (64-bit build, READ; the 32-bit counterparts exist and were not compared
instruction by instruction): the startup wrapper keeps the 64-session initialization, the 30 s
IOTC alive timeout, the always-allow port callback, the account comparison with the configured
password handed to the SDK callback, and the tunnel server start with its authentication and
session callbacks. It adds one retry: when initialization returns -30007 it de-initializes and
retries once ([sdk-licence.md: Device-side SDK start](../../auth/cloud-auth/sdk-licence.md#device-side-sdk-start)). There is
still no wrapper-level allow-list of forwarded ports: the app's nine mappings and the server's
authorization are distinct. The tunnel login exchange (opcode 7 answered by 08 or 09, 1004-byte read,
90000 ms login timeout, 30000 ms RDT create) is unchanged.

R70. The TCP receive-buffer setter applies `SO_RCVBUF` only when set nonzero (0 keeps the OS
default). It is unrelated to the tunnel threshold and does not define an RDT window. READ.

## Port-mapping profile

R71. The app opens **two** tunnel sessions (separate IOTC sessions) and maps nine ports. The
remote port is what SETUP carries; the local port is the app's listener choice and is
configurable. Labels are app names, not service IDs. READ.

| Session | App label | Local TCP -> remote TCP | Remote service |
|---|---|---|---|
| primary | SOCKET | 4700 -> **4700** | JSON control, see [control](../../control/session-handshake.md) |
| primary | FW_SOCKET | 4350 -> 4350 | updater JSON |
| secondary | HTTP | **8080 -> 80** | HTTP |
| secondary | RTMP | 4554 -> 4554 | RTSP video stream |
| secondary | RTMP_WIDE | 4555 -> 4555 | wide-camera RTSP video stream |
| secondary | FILE | 4801 -> 4801 | file transfer |
| secondary | PIC | 4800 -> 4800 | image transfer |
| secondary | PIC_WIDE | 4804 -> 4804 | wide-camera image transfer |
| secondary | FW_UPLOAD | 4361 -> 4361 | firmware upload |

The `RTMP` and `RTMP_WIDE` labels are the app's own names for the 4554 and 4555 entries. READ. The app dials these ports with the scheme `rtsp://` (`rtsp://<host>:4554/stream` and `rtsp://<host>:4555/stream`). READ. That the device speaks the RTMP protocol on these or any other ports is not established; see [video.md](../../media/video.md#rtsp-endpoints).

The "Remote service" column is a reading of the labels; see [ports.md](../ports.md#remote-tunnel-port-mapping) for the
services. INFERRED. SMB port 445 is **not** mapped. READ. A client MUST NOT assume an SMB
tunnel. The device would forward one on request ([ports.md R13a](../ports.md#remote-tunnel-port-mapping)).

R72. Connection order. READ: connect the first session; if it succeeds and the attempt is
still current, connect the second (Android app 3.3.2; the iOS app 3.4.0 does not follow this order, see R72a); require both results nonnegative; map the primary list on
the first session, then the secondary list on the second. The mapping runner stops at the
first failure or cancellation. Stale-attempt checks before session validation, before mapping
and after mapping route to cleanup, which removes created mappings and valid sessions.

R72a. iOS app 3.4.0 connect ordering (READ). The app's tunnel client builds one connect object per
`connectInfo` entry it holds, dispatches every one at once on a global queue and waits for the group with
a timeout of "forever". Each block calls the tunnel agent's single-target connect (not its parallel
connect entry point). The first success wins; later completions are logged and ignored. How the
`connectInfo` list is composed (how many entries, and whether they are the two Seestar tunnels or
alternative paths to one tunnel) was not decoded, so whether this changes the ordering of the primary
and secondary sessions of R72 is unresolved. A client written against this chapter MAY still use the
sequential order of R72. Android app 3.3.2 is unchanged.

## Readiness and reconnect

R73. A successful tunnel and mapping result means transport connected, not device ready.
The app then waits up to **30000 ms** for matching device-state information over the control
port. On timeout it disconnects and reports local code -10087 ("remote device info
timeout"). This deadline is separate from the workflow connection budget and the RDT/DTLS
handshake timeout, both also 30000 ms. It is not a wire result. READ.

R74. Reconnect. READ: only status -30006 triggers it; it is suppressed during a manual
disconnect; a per-session-ID set debounces repeat notifications (no timer; reset clears it);
callbacks are ignored when cancelled or not connected; a pending reboot leads to cleanup
without reconnect; otherwise a single-flight flag admits one reconnect.

R75. A reconnect tears down old state, fetches device detail again, calls `online-link`
again and connects with the new licence, device ID, credentials and connection ID. The code
establishes no fixed retry count or cooldown. READ. Whether the new values differ from the old ones, and
cloud expiry and allocation reuse, are unresolved (server-side).

R76. A client SHOULD treat -30006 as "session gone", release all local listeners' channels,
and obtain fresh cloud credentials before reconnecting. INFERRED.

## Minimal outbound proxy profile

R77. The minimal useful client is a **TCP byte proxy**: one local listener forwarding remote
port **4700** over one authenticated tunnel. It ends at forwarded TCP bytes and does not
parse requests. Two sessions and the other eight mappings are needed only for app parity.
INFERRED (a selection from READ behaviour; not a vendor-defined profile).

What it needs from each layer (INFERRED):

| Layer | Required | Optional |
|---|---|---|
| Cloud | existing account authorization; device selection; `online-link` for licence, device ID and credentials; allocation stop; fresh attempt state on reconnect ([cloud-auth](../../auth/cloud-auth.md)) | account enrolment, sharing and other account features |
| Discovery / rendezvous / IOTC | master and P2P-server discovery including UDP hello, direct and relay rendezvous with UDP/TCP racing, direct and relay data, alive and close ([IOTC session](../iotc/index.md)) | device-side registration; LAN search only for local discovery |
| DTLS | packet-preserving DTLS; identity = username bytes; PSK = SHA-256 of the password bytes; see [RDT](../rdt.md) | plain RDT is not the authenticated profile; never fall back silently |
| RDT | creation, DATA, ACK and selective ACK, retransmission and flow control, FIN/QUIT/ABORT/EXIT; parse all established operations ([RDT](../rdt.md)) | sending urgent DATA |
| Tunnel | LOGIN and result; port verification as the app does it; SETUP, DATA, END, CLOSE; receive PAUSE/RESUME/WAKE; stream reassembly; half-close, drain and cleanup | service mapping, attached sessions, LAN-direct bypass |
| Seestar | one mapping to remote 4700; reconnect on -30006 | second session and all nine mappings; app readiness guards |

R78. A robust proxy MUST handle both direct and relay paths, cancellation and stale
attempts. A UDP-only subset is narrower and can fail on restricted networks. INFERRED.

## First application bytes on port 4700

This sits above the tunnel; it is the recovered behaviour of the app's control client, not a
captured reply. See [session handshake](../../control/session-handshake.md) and the
[`get_device_state`](../../../docs/control/methods/get_device_state.md) card.

R79. Request. READ: the app numbers commands from a counter (return, then increment), builds
`id`, `method` = `get_device_state`, `params.keys` = `["client","camera","second_camera"]`
in that order, adds no `jsonrpc` member, appends CR LF and sends it as UTF-8. Example with
id 1 (member order illustrative), followed by `0d 0a`:

```json
{"id":1,"method":"get_device_state","params":{"keys":["client","camera","second_camera"]}}
```

R80. Replies and events. READ: the app reads UTF-8 lines. A line containing the substring
`jsonrpc` is a reply candidate; other lines go to event handling. A reply is decoded only if
its `id` equals the pending command's id; a lower id is skipped; a higher id raises an error in
that branch. `code` 0 means success.

R81. A client above the proxy MUST split the TCP byte stream into lines across arbitrary
TCP, tunnel, RDT and DTLS boundaries, keep a partial line for the next read, accept LF, CR or
CR LF as terminators, and match replies to requests by `id`. A reply or event need not fit one
DATA frame. INFERRED. The device ends a request line at any CR or LF byte and ignores a
`jsonrpc` member in a request; CR LF is not required. READ ([ports.md: Framing per port family](../ports.md#framing-per-port-family)).

R81a. Secure communication over the tunnel (firmware 9.75). Requests that arrive over the tunnel
reach the device as loopback connections; see [ports.md R15 and R15a](../ports.md#remote-tunnel-port-mapping).
The field-encryption layer is independent of the tunnel's own encryption. A tunnel client is not
required to obtain the key envelope to use the control port, but Wi-Fi password operations and the
password member of the device state need an established crypto session, which the app obtains only through
`get_verify_str` and `verify_client` on the same stream
([secure communication](../../control/secure-communication.md)). The loopback classification chain (the accepted peer address compared with the address of `localhost`, then the connection's external flag cleared so the connection counts as verified) is READ in
both firmware versions; that the app requests loopback as the destination, so that tunnel streams
arrive from the tunnel daemon on loopback, and the 32-bit parity, are INFERRED. The readiness check
of R73 is unaffected: `get_device_state` without a session omits the access-point password rather than
failing.

## Synthetic layered byte example

All values are synthetic; no credentials, keys or live identifiers. INFERRED (a structural
fixture built from the layouts in this and the neighbour chapters; real packetization may
differ).

Assume an authenticated direct session, a channel opened to remote port 4700 on tunnel
channel 7, peer RDT ID 9, and a 43-byte payload that fits one DATA frame, one RDT packet and
one DTLS record. `example` is a fictitious method, not a Seestar command.

```text
Application TCP bytes (43):
  {"jsonrpc":"2.0","id":1,"method":"example"}
  7b 22 6a 73 6f 6e 72 70 63 22 3a 22 32 2e 30 22 2c 22 69 64 22 3a
  31 2c 22 6d 65 74 68 6f 64 22 3a 22 65 78 61 6d 70 6c 65 22 7d

Tunnel DATA frame (47):
  02 07 2b 00 | 43 TCP bytes
  opcode 02, channel 7, LE16 L = 43

RDT DATA packet (67):
  5a 97 c2 f1 02 05 2f 00 01 00 00 00 00 00 00 00 01 09 00 00 | 47 tunnel bytes
  RDT magic, type DATA (02), version 05, LE16 length 47,
  sequence (low 1, high 0), transmit count 1, peer ID 9, reserved 0

DTLS 1.2 application-data record (96):
  17 fe fd 00 01 00 00 00 00 00 02 00 53 | CIPHERTEXT[67] | TAG[16]
  content type 23, version DTLS 1.2, epoch 1, sequence 2,
  BE16 length 83; AEAD suite with no explicit nonce and no padding assumed

IOTC packet prefix (28):
  04 02 1d 0b 6c 00 01 00 07 04 21 00 44 33 00 01
  0c 00 00 00 44 33 22 11 88 77 66 55 | 96 DTLS bytes
  magic 0204, revision 29, flags (partial transform, little-endian, extended RID),
  LE16 body length 108, IOTC sequence 1, opcode 0407 (direct data), route 21,
  H+12 = low 16 bits of the RID (44 33), IOTC channel 0, datatype 1,
  LE32 extension length 12, synthetic 8-byte RID

UDP payload (124):
  Transform_K(IOTC packet[0:64]) || IOTC packet[64:124]
```

Notes (INFERRED unless marked):

- Lengths check: 4 + 43 = 47; 20 + 47 = 67; 13 + 67 + 16 = 96 with `0x53` = 83 = 67 + 16;
  16 + 12 + 96 = 124 and the IOTC body length is 12 + 96 = 108. UDP length would be 132.
- The direct sender copies the low 16 bits of the first RID word into H+12 even with an
  extended RID, hence `44 33`. READ.
- `Transform_K` is the legacy prefix obfuscation, keyed from the licence mask, over the first
  64 IOTC packet bytes (the 28-byte prefix and the first 36 DTLS bytes). READ (coverage).
  Its output, the ciphertext and the tag are left symbolic.
- On a relay path the IOTC opcode, route, relay ID and destination change; the nesting
  tunnel -> RDT -> DTLS does not. There is no extra length prefix or rendezvous GCM envelope
  around peer data. READ.
- The device reverses the transform, authenticates and decrypts DTLS, orders RDT, parses the
  tunnel DATA frame and writes the original 43 bytes to its TCP socket for port 4700.
