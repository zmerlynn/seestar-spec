# P2P tunnel (TCP port forwarding)

This chapter specifies the P2P tunnel layer: the framing that carries many TCP connections
over one authenticated, reliable byte stream between the app and the device. Below it is
[RDT](../rdt.md) (reliable, ordered, DTLS-protected stream on IOTC channel 0, itself over the
[Kalay IOTC session](../iotc/index.md)). Above it are ordinary application TCP
services, chiefly the JSON control port 4700 ([session handshake](../../control/session-handshake.md));
the full port list is in [ports.md](../ports.md).

| File | Contents |
|---|---|
| [framing.md](framing.md) | Frame envelope, message catalogue, login / authentication / versioning, port and service verification (R1-R27) |
| [channels.md](channels.md) | Listeners, channel allocation and reuse, SETUP, DATA, half-close and close, PAUSE / RESUME / WAKE (R28-R53) |
| [session.md](session.md) | Teardown, timers and limits, API errors versus wire results, LAN-direct and attached sessions (R54-R67) |
| [seestar-profile.md](seestar-profile.md) | Seestar app and device integration, the nine port mappings, readiness and reconnect, minimal proxy profile, first bytes on 4700, layered byte example (R68-R81) |

## Conventions

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are used as in RFC 2119 and RFC 8174.
They bind a client (or a stand-in for either endpoint); sentences about what "the app" or "the
device" does are descriptions.

Labels (see `CONVENTIONS.md`):

- **READ**: static analysis of the app 3.3.2 tunnel library and Java code, or of the firmware
  9.31 imager (64-bit build; the 32-bit build was checked for login, dispatch, socket reader,
  quarantine and buffer threshold and agrees).
- **OBSERVED**: seen on a live device, with the date. Only the setup order and timing in [Observed session setup](#observed-session-setup)
  and one live PAUSE use (channels.md R53) are observed; no tunnel bytes were decoded.
- **INFERRED**: a consequence, interpretation or proposed implementation policy.
- **unresolved**: not established.
- **DOC**: the vendor's public SDK integration guides. They describe the API, not these bytes.

Byte values are hexadecimal. "LE16"/"LE32" are little-endian unsigned integers, "BE16"
big-endian. Integers in tables are decimal unless written `0x..`.

## Terms

- **Agent**: the endpoint that opens local TCP listeners and forwards accepted connections
  (the app). **Server**: the endpoint that connects forwarded channels to real local services
  (the device). DOC (vendor terms); both binaries contain both roles. READ.
- **Session**: one tunnel over one IOTC session and one RDT endpoint on IOTC channel 0. READ.
- **Tunnel channel**: an 8-bit index (0-255) in each frame that names one forwarded TCP
  connection. It is independent of the IOTC channel, the RDT peer ID, the IOTC session ID, the
  cloud connection ID and the API's mapping index. READ.
- **Mapping**: an Agent listener that sends every accepted connection to one remote port.

```text
 local TCP client        Agent (app)                         Server (device)
  e.g. JSON client  --> listener :4700 --+                 +--> <loopback>:4700 (control)
                         listener :4801 -+-- channels 0..255 --> <loopback>:4801 ...
                                          |  tunnel frames  |
                                          +=== RDT stream ==+   (DTLS-PSK, IOTC channel 0)
                                          +=== IOTC session (direct or relay, UDP or TCP) ===+
```

## Overview

1. The app gets credentials from the cloud, opens an IOTC session to the device and creates
   an authenticated RDT stream on IOTC channel 0. ([cloud-auth](../../auth/cloud-auth.md),
   [IOTC](../iotc/index.md), [RDT](../rdt.md))
2. It sends LOGIN (`07`); the device answers PASS (`08`) with capability flags.
3. For each mapped port it may verify the port (`0c`/`0d`), then listens locally.
4. Each accepted local connection gets a free channel and a SETUP (`01`) naming the remote
   port. Bytes then flow as DATA (`02`) both ways.
5. END (`03`) half-closes one direction; CLOSE (`04`) aborts the channel. PAUSE / RESUME /
   WAKE (`05`/`06`/`07`) throttle a channel's local reads.
6. The session ends with RDT/IOTC; there is no tunnel logout.

The tunnel adds no framing of its own to the forwarded bytes. A 4700 stream through the tunnel
uses the same line rules as on the LAN: the device ends a request line at any CR or LF byte (a CR
LF pair is not required), ignores lines of 4 bytes or fewer, and ignores a `jsonrpc` member in a
request rather than rejecting it. READ. See
[session handshake R8](../../control/session-handshake.md) and [ports.md: Framing per port family](../ports.md#framing-per-port-family).

## State summary

These state names are editorial, not wire values. READ.

Session (Agent):

| State | Event | Next state / action |
|---|---|---|
| idle | connect | IOTC up, RDT create + DTLS -> `login-sent` after sending `07` |
| login-sent | `08` | `active`; start dispatch, socket reader and sender workers |
| login-sent | `09`, other opcode, RDT error or 30000 ms timeout | tear down RDT and owned IOTC -> `idle` |
| active | IOTC loss (-30006), RDT error, disconnect or abort | release all channels, stop workers, destroy/abort RDT -> `idle` |

Session (Server):

| State | Event | Next state / action |
|---|---|---|
| listening | IOTC session accepted | RDT create + DTLS -> `await-login` |
| await-login | `07` | callbacks; send `08` (or `09`, see R18) -> `active` |
| await-login | other first byte, error, 90000 ms timeout | destroy RDT, close IOTC |
| active | session ends | abort RDT, 1 s, close IOTC, 1 s |

Channel (either end):

| State | Event | Next state / action |
|---|---|---|
| free (0) | Agent accepts local TCP | send SETUP -> `active` (no acknowledgement) |
| free / any | Server receives SETUP | verify, connect -> `active`; or send CLOSE (1 or 2) -> `quarantine` |
| active | local read ends, W=0 | send END; R=1 |
| active | END received | drain, then shut down local write; W=1 |
| active | both directions ended, or terminal I/O error | release -> `quarantine` (some paths send CLOSE 1, see flag table) |
| active | CLOSE received | release at once -> `quarantine` |
| quarantine (2..30) | 1 s sweep | increment; above 30 -> `free` |

See [channels.md](channels.md#data-half-close-and-close) for the exact flag table.

### Observed session setup

Three remote sessions from an Android client to a live device (2026-10-10, 2026-10-11,
2026-10-13; firmware and app versions not recorded) all set up in the same visible order and
reached a working 4700 session. OBSERVED.

| Stage reached | Elapsed since previous stage (ms, three runs) |
|---|---|
| Allocation (`online-link`) completed | 2502-2514 from request |
| IOTC session established (direct UDP) | 216-395 |
| DTLS ready (version `FE FD`, cipher suite `CC AC`) | 118-126 |
| RDT channel established | 161-263 |
| Tunnel login completed | 121-204 |
| First 4700 reply (code 0) | 302-414 |

Times are differences between client log timestamps, not packet transit times. The individual
channel-open exchange and the numeric result codes of each stage were not recorded, so the last
interval includes channel open and the first request. OBSERVED. The order matches the static
sequence in this chapter and [sdk-licence.md](../../auth/cloud-auth/sdk-licence.md#client-hand-off).

## Open questions

- Interoperability of an independent tunnel implementation is untested; the official client was
  observed to complete setup ([Observed session setup](#observed-session-setup)), but the channel-open exchange and per-stage result codes were
  not captured. unresolved.
- Login reads are single reads. The device Server writes its result in one RDT write, so a split
  result is not expected from deployed devices
  ([framing.md R19](framing.md#login_pass--login_reject-08--09-server---agent)); this is not captured. The device Server
  does not reassemble a split LOGIN (framing.md R19a); whether the app's LOGIN ever arrives split,
  and the 1000-byte API allowance versus the 1004-byte Server read, need a capture. unresolved.
- The stored-index rejection quirk, simultaneous closes, SETUP during quarantine and late DATA
  after index reuse: local actions are READ; frequency and ordering are unresolved.
- Flow-control timing: whether the last read after PAUSE happens in practice and how the shared
  RDT receive count affects sibling channels
  ([channels.md R52](channels.md#backlog-after-pause)). unresolved. The real burst after
  PAUSE: see [channels.md R53](channels.md#backlog-after-pause).
- App orchestration: full coroutine cancellation interleavings. unresolved. Runtime choice of
  LAN-direct: see Q29 in [00-overview.md: Open-question register](../../00-overview.md#open-question-register).
- The legacy 16-byte SETUP and short PASS handling prove compatibility branches, not a
  version-negotiation scheme; other tunnel versions are out of scope. unresolved.
- Firmware 9.75 and iOS app 3.4.0: the tunnel wire protocol is unchanged (READ), but the iOS
  client's connect ordering is READ (one connect per entry, first success wins, forever wait; R72a), but
  how its entry list is composed, its handling of cancellations and the 32-bit device counterparts were not
  compared; see [seestar-profile.md R69a, R72 and R72a](seestar-profile.md#port-mapping-profile). unresolved.
- Cryptography (suites, key derivation, nonces, handshake retransmission) is not in the
  tunnel layer; it belongs to [RDT](../rdt.md).

## Appendix: How to validate on a live device (non-normative)

Proposed only; none was done. Use an owned device and isolated session; keep no credentials,
authentication data or forwarded contents. INFERRED.

1. Capture the official app passively (connect, map, transfer, disconnect). Ciphertext
   offsets are not tunnel fields.
2. On an authorized test install, log direction, session, opcode, channel, length and time at
   the RDT read/write boundary. Check header layout, `07` login versus wake, verification
   echoes and the 52-byte SETUP.
3. Through a harmless test TCP endpoint, send fragmented writes and half-close each direction
   in turn: queued bytes drain before write shutdown, the reverse direction continues after
   one END, CLOSE releases without reply.
4. Slow the receiving consumer to see PAUSE, WAKE and RESUME near the thresholds; then
   open and close connections repeatedly to time index reuse.
5. Use a closed test port to see CLOSE result 1. Rejection (result 2) needs a controlled test
   server, since the device always accepts the port.
6. Test a new implementation first against synthetic frames in a local harness, then against
   the test device. Keep malformed-length tests in the harness.
