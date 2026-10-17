# P2P tunnel: framing, login and verification

Part of the [P2P tunnel chapter](index.md). This file covers the tunnel frame envelope, the
message catalogue, session login (version and capability exchange) and the port and service
verification exchanges. The frames travel inside the authenticated [RDT](../rdt.md) byte
stream; channel setup and data forwarding are in [channels.md](channels.md).

Basis for this file: static analysis of the app's tunnel library (app 3.3.2, tunnel version
`0x04030800`) and the firmware 9.31 imager (tunnel version `0x04030603`), both builds.

## Frame envelope

R1. Every tunnel message is one frame: a 4-byte header followed by `L` payload bytes. There is
no magic, version, sequence number, acknowledgement, checksum, MAC or nonce in the frame. READ.

| Offset | Size | Type | Endianness | Meaning |
|---:|---:|---|---|---|
| 0 | 1 | u8 | - | Opcode |
| 1 | 1 | u8 | - | Tunnel channel index (0-255); session-level messages use 0 |
| 2 | 2 | u16 | little | Payload length `L`; excludes the 4 header bytes |
| 4 | L | bytes | - | Payload; the next frame begins at offset `4 + L` |

R2. Multi-byte tunnel integers are little-endian, with one exception: the embedded
`sockaddr_in` port and address in SETUP are in network byte order ([Login, authentication and versioning](#login-authentication-and-versioning) of
[channels.md](channels.md)). READ.

R3. Frames are written to RDT as header plus payload in one write and read back from the RDT
byte stream. Reliability, ordering and encryption belong to RDT and IOTC, not to this layer.
READ.

R4. A receiver MUST reassemble frames from the RDT byte stream: a frame can span several RDT
reads and one read can hold several frames. It MUST keep surplus bytes for the next frame and
MUST NOT equate an RDT read, an RDT packet or a UDP datagram with a frame. INFERRED (from the
exact-read helper below and 8192-byte socket chunks).

R5. In the established state the native receiver reads exactly 4 header bytes, then exactly
`L` payload bytes. Each underlying RDT read uses a 100 ms timeout; a timeout or zero-progress
read is retried while the session is active; any other negative result ends the handler. A
zero-length payload needs no read. READ.

R6. A receiver SHOULD enforce a local bound on `L` (and on each layout below) before
allocating or copying. INFERRED. The native receivers do not: their scratch buffer is 8196
bytes while `L` can reach 65535. That omission is not a requirement to reproduce. READ.

## Message catalogue

Names are from diagnostic strings in the binaries where present; "both" means both library
implementations can send it, not that Seestar uses both directions. READ.

| Opcode | Session state | Payload `L` | Name | Direction |
|---:|---|---:|---|---|
| `01` | established | 52 (current); 16 (legacy) | SETUP_SERVICE | Agent -> Server; opens a channel |
| `02` | established | 1-8192 as sent | DATA | both |
| `03` | established | 0 | DATA_END | both; end of one direction |
| `04` | established | 1 as sent; 0 accepted | DATA_CLOSE | both; full channel close |
| `05` | established | 0 | PAUSE | both |
| `06` | established | 0 | RESUME | both |
| `07` | established | 0 | WAKE | both |
| `07` | awaiting login | 8 + N | LOGIN_AUTH | Agent -> Server |
| `08` | awaiting login result | 8 | LOGIN_PASS | Server -> Agent |
| `09` | awaiting login result | 8 | LOGIN_REJECT | Server -> Agent |
| `0c` | established | 6 | PORT_VERIFY_REQS | Agent -> Server |
| `0d` | established | 6 | PORT_VERIFY_RESP | Server -> Agent |
| `0e` | established | 36 | SERVICE_VERIFY_REQS | Agent -> Server |
| `0f` | established | 36 | SERVICE_VERIFY_RESP | Server -> Agent |

The "Agent" is the endpoint that opens local TCP listeners (the app); the "Server" is the
endpoint that connects to the real services (the device). See the [index](index.md#terms).

R7. Opcode `07` means LOGIN_AUTH only as the first frame of a session and WAKE afterwards. An
implementation MUST interpret `07` by session state. READ.

R8. No builder or handler exists for `00`, `0a`, `0b` or values above `0f`. In the
established state the native receiver consumes an unknown frame by its length and sleeps
100 ms. `08` and `09` have meaning only to the login reader. READ. A new implementation SHOULD
skip unknown frames by length and MAY log them. INFERRED.

R9. Opcodes `03` to `07` act only on an active channel (slot state 1); on an inactive channel
they have no effect. `0c` to `0f` are processed without an active data channel. READ.

## Login, authentication and versioning

### Sequence

```text
Agent (app)                                            Server (device)
  | IOTC session up (see kalay-iotc-session)              |
  | RDT create on IOTC channel 0, 30000 ms, DTLS-PSK  <-->| RDT create, 30000 ms
  |-- 07 00 L=8+N : version, N, auth[N] ---------------->| one read, up to 1004 B, 90000 ms
  |                                                       | session-info callback(s)
  |<-- 08|09 00 L=8 : result, capability flags ----------| 
  | one read, 16 B, 30000 ms                              |
  | 08: session active, workers start                     | forwarding handler starts
  | 09: tear down, API result -30008                      |
```

R10. The Agent creates RDT on IOTC channel 0 with a 30000 ms timeout, sends LOGIN once, then
reads the result once (16-byte buffer, 30000 ms). With an authentication callback it uses the
authenticated (DTLS) RDT client create; without, plain RDT create. READ.

R11. A Seestar client MUST use the authenticated RDT create. Credentials (username and
password from the cloud handoff) are given to RDT, not carried in LOGIN. READ (app binding);
see [RDT](../rdt.md) and [cloud authorization](../../auth/cloud-auth.md).

### LOGIN_AUTH (`07`, Agent -> Server)

| Payload offset | Size | Type | Endianness | Meaning |
|---:|---:|---|---|---|
| 0 | 4 | u32 | little | Sender tunnel version |
| 4 | 4 | u32 | little | Legacy authentication-data length `N` |
| 8 | N | bytes | - | Opaque legacy authentication data |

R12. The app's normal connection sends `N = 0`, giving the 12-byte frame
`07 00 08 00 | 00 08 03 04 | 00 00 00 00`. READ.

R13. The Android app 3.3.2 advertises version `0x04030800`; firmware 9.31 and 9.75 advertise
`0x04030603`; the iOS app 3.4.0 also reports `0x04030603` (READ, SDK 4.3.6 build 3). The
Server passes the received version to its session callback and does not require it to equal
its own. There is no version negotiation beyond this. READ.

R14. The legacy APIs accept 0 to 1000 bytes of authentication data (frame up to 1012 bytes),
but the Server's initial read requests only 1004 bytes. This mismatch is in the code; it is
not a proven usable maximum. READ. A client SHOULD send `N = 0`. INFERRED.

### LOGIN_PASS / LOGIN_REJECT (`08` / `09`, Server -> Agent)

Twelve bytes: opcode, channel 0, `L = 8`, then:

| Payload offset | Size | Type | Endianness | Meaning |
|---:|---:|---|---|---|
| 0 | 4 | s32 | little | Server callback result; 0 on pass, negative legacy result on reject |
| 4 | 1 | u8 | - | Nonzero if a port-verification callback is registered |
| 5 | 1 | u8 | - | LAN-direct/proxy enable flag |
| 6 | 1 | u8 | - | Nonzero if a service-verification callback is registered |
| 7 | 1 | u8 | - | 0 |

Pass and reject differ only in the opcode and result; the flags are present in both. READ.

R15. Agent handling. READ:

- `09`, or any first byte other than `08`/`09`: tear down RDT and the owned IOTC session;
  API result -30008.
- `08` with `L >= 8`: nonzero flags normalize to 1.
- `08` with `L` in 0-7: accepted as pass, port verification disabled, service capability
  "unknown" (-1). No value in that range is rejected.
- The compared value is the header `L`, not the byte count actually read. The read buffer is
  zeroed first, so a flag byte not actually received reads as 0.
- The signed result of an `08` is not inspected; a negative result with `08` still passes.

The boundary is therefore set by the header `L` alone. The Agent reads at most 16 bytes into a
zeroed buffer. Port verification comes from payload byte 4 and service capability from payload
byte 6; payload byte 5 is not read here. READ. Outcomes:

| Received | Result |
|---|---|
| Read error | Tear down; error result |
| No bytes, or a first byte other than `08`/`09` | Tear down; -30008 |
| `08`, header `L` 0–7 (including a delivery too short to contain `L`, which reads as 0) | Pass; port verification off; service capability -1 |
| `08`, header `L` ≥ 8, all 12 bytes received | Pass; flags from payload bytes 4 and 6, normalized to 0/1 |
| `08`, header `L` ≥ 8, fewer than 12 bytes received | Pass; each missing flag reads 0, so service capability is 0 (known off), not -1 |

READ. The received byte count is never compared with `L`.

A client MAY be stricter (for example reject `08` with `L < 8`); that is local policy, not a
native requirement. INFERRED. The device firmware, the only Server in the Seestar profile, sends
a 12-byte result (`L = 8`, R19); other Servers are out of scope.

R16. On pass the Agent marks the session active, sets the default buffer threshold 512000
([channels: Pause, resume and wake](channels.md#pause-resume-and-wake)) and starts the tunnel and socket-reader workers. READ.

R17. Server handling. READ: create RDT on IOTC channel 0 (30000 ms; authenticated create when
authentication is configured); read up to 1004 bytes once with a 90000 ms timeout; a negative
result or a first byte other than `07` destroys RDT and closes the owned IOTC session. With
`L = 0` it takes the pass path. Otherwise it calls the configured extended session callback
(a notification after RDT authentication, not a password check) or the legacy callback with
version and opaque data; a negative legacy result selects `09`.

R18. Quirk: the threaded Server path sends `09` and still enters its forwarding handler. The
Agent closes on `09`. A stand-in Server SHOULD close after sending `09`. READ (quirk),
INFERRED (advice).

R19. The login reads are single reads without the accumulation loop of R5. The device
Server's handling of a split LOGIN is in R19a. The app Agent reads the result with one RDT read
of up to 16 bytes (30000 ms timeout) and makes no second read. Only a negative return is
checked. A split result is decided from the first delivery alone by the R15 table, and the login
code does not drain the bytes still to come. READ (app library, SDK 4.3.8). Those bytes stay in
the RDT stream and the established-state reader of R5 takes them as the start of the next frame.
INFERRED. A new implementation SHOULD
accumulate the 4-byte header and `L` bytes as in R4. INFERRED.

R19a. The device Server reads the LOGIN with one RDT read of up to 1004 bytes and has no
reassembly loop. The RDT read returns the bytes available at that moment. The Server checks the
first byte, then copies the authentication payload by the header's length `L`, not by the number
of bytes the read returned. A LOGIN split across RDT deliveries is therefore processed from the
first read alone, and the copied payload can include bytes that never arrived. READ. The device
relies on the normal 12-byte LOGIN arriving in one delivery. An Agent SHOULD send the LOGIN in
one RDT write. INFERRED.

The device Server (firmware 9.31, both builds, threaded and non-threaded paths) sends its
12-byte `08` or `09` result with one RDT write of `L + 4` bytes, as the first write on the new
RDT connection. The device's RDT write copies a write that fits the free payload space into one
outgoing packet under its global lock, and splits a write only when it would overflow that
space. READ. Deployed device Servers are therefore not expected to split the result, and an
Agent that accumulates to `L` gets the same outcome as the native single read. INFERRED; no
capture exists. A new Agent SHOULD therefore accumulate exactly 4 header bytes and then `L`
bytes, read nothing beyond the frame, and SHOULD NOT reproduce the short-delivery rows of the R15
table as required behaviour; they describe the native reader only. INFERRED. Servers other than
the device firmware are out of scope.

### Device credential policy

R20. The device's RDT credential callback compares the incoming account with its configured
account and supplies its configured password on a match; an unknown account gets no password.
Its port-verification callback logs and returns 0 (allow) unconditionally. Its session
callback requests a buffer threshold of 5120000 bytes. No service-verification callback is
registered in the inspected startup path. READ (firmware 9.31, both builds for the threshold).

## Port and service verification

### Layouts

Port verification, `0c` request / `0d` response, channel 0, `L = 6`:

| Payload offset | Size | Type | Endianness | `0c` request | `0d` response |
|---:|---:|---|---|---|---|
| 0 | 2 | u16 | little | Correlation ID | Copied ID |
| 2 | 2 | u16 | little | Requested port | Copied port |
| 4 | 1 | u8 | - | 0 | 1 if the callback result is >= 0, else 0 |
| 5 | 1 | u8 | - | 0 | 0 |

The verification port is little-endian, unlike the SETUP port. A missing callback means
allowed. READ.

Service verification, `0e` request / `0f` response, channel 0, `L = 36`:

| Payload offset | Size | Type | `0e` request | `0f` response |
|---:|---:|---|---|---|
| 0 | 2 | u16 LE | Correlation ID | Copied ID |
| 2 | 33 | bytes | Service ID, at most 32 bytes, NUL-terminated, zero-filled | Copied service ID |
| 35 | 1 | u8 | 0 | 1 if the service callback returns a nonzero port, else 0 |

Receive handling (READ, device and app libraries): neither side checks `L` exactly for `0c`–`0f`;
receivers read fixed offsets. The `0c` receiver reads only the ID and port; request bytes 4–5
are ignored. The `0e` receiver reads the ID and the service ID as a C string (only emptiness is
tested); request byte 35 is ignored. The Agent accepts a `0d` or `0f` only when its ID equals the
pending ID. For `0d` it then requires the returned port to equal the requested port (-30027
otherwise), never reads byte 5, and tests validity as **nonzero** (zero gives -30033). For `0f`
it compares the returned service ID with the request over the request's length only (a prefix
match; mismatch -30027) and tests byte 35 as nonzero (zero gives -30033).

R20a. A sender MUST send validity as exactly 0 or 1 and zeros in the unused bytes. A receiver
MUST ignore request bytes 4–5 (`0c`) and 35 (`0e`) and response byte 5 (`0d`), and SHOULD treat
any nonzero validity as allowed, as the official Agent does. A receiver SHOULD compare the
returned service ID exactly up to its NUL rather than as a prefix. INFERRED (policy).

The service ID character set is not specified. The resolved port is not returned; SETUP asks
the callback again. Empty service ID or no callback is invalid. READ.

### Agent behaviour

R21. The Agent skips port verification when the login flag says it is disabled. Otherwise it
sends one request, records the pending ID, and polls every 100 ms for `timeout / 100` rounds.
Normal mapping uses 5000 ms; the LAN-direct path uses 1000 ms. There is no retransmission.
READ. On the normal path the request is sent once when a port mapping is created, before its
listen index is allocated, not once per local TCP connection; a timeout fails the mapping, and
the app then abandons the whole connection attempt and releases its sessions, so a new request
for the same port comes only with a new connection attempt. The LAN-direct accept path retries
only on "another request pending" (-30034), at most three attempts 500 ms apart, and closes the
accepted local socket on any other failure. On timeout or a port mismatch the Agent zeroes the
pending ID, so a late response no longer matches (R24). READ. The device side keeps no state
for these requests and answers each one independently, copying the ID and port ([Layouts](#layouts), R20). READ. Re-sending with a fresh ID on
the same session is therefore not app behaviour; a client that does so SHOULD keep R26 and
document it as its own policy. INFERRED.

R22. Service verification needs service capability exactly 1, else -30036. Normal wait is
50 x 100 ms. READ.

R23. Results (local API codes, see [session.md](session.md#api-errors-versus-wire-results)):
another request pending -30034; write failure -30017; no response -30030; returned port
mismatch -30027; validity 0 -30033. Service verification reuses these codes. READ.

R24. The dispatcher records a response only when its ID equals the pending ID; the waiter
treats a nonzero returned port as completion, and for services compares the returned name to
the requested one. READ.

R25. The native ID is `(random + time) mod 65536`, with `0xffff` mapped to 0; 0 also means
"nothing pending", so the native code can generate an ID that never completes. It is
correlation, not a cryptographic nonce. READ.

R26. A client SHOULD keep at most one outstanding request of each kind per session, use a
nonzero ID, and accept only a response matching the outstanding ID and the requested
port or name. INFERRED. Receivers compare for equality only and do not check how the ID was
made. READ.

R27. The Seestar app uses port mapping, not service mapping (READ), and the device's port
callback always allows (R20). A client SHOULD perform port verification when the login flag
enables it, as the app does; service verification is optional. INFERRED.
