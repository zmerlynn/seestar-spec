# RDT session lifecycle

Part of the [RDT chapter](../rdt.md). This file covers connection identity, creation and the
HEARTBIT exchange, the optional DTLS secure channel, and close, abort and failure. It sits on an
IOTC session and channel ([Kalay/IOTC session](../kalay-iotc-session.md)); the stream it
establishes is used by the [P2P tunnel](../p2p-tunnel.md). Packet layouts:
[framing](framing.md). Labels: [rdt.md: Conventions](../rdt.md#conventions).

Basis: static analysis of the RDT create, receive, send-thread, destroy and abort paths in app
3.3.2 and firmware 9.31, and of the secure-channel adapter in the app's IOTC library and the
64-bit firmware.

## Connection identity

R26. An RDT connection is bound to an existing nonnegative IOTC session ID (SID) and a one-byte
IOTC channel. At most one RDT connection exists per `(SID, channel)`; a second create on an
occupied pair fails. READ. The local RDT handle is an index into a process table (128 entries
initially) and is never sent. READ.

R27. Each connection also gets a one-byte **specific ID**. The allocator starts at 1 and cycles
1, 2, ..., 254, 1, ... (0 and 255 are never allocated). When a table slot is reused, it
remembers the previous remote ID it had. READ.

R28. Receive lookup. A HEARTBIT, or any packet whose byte 17 is 0, is matched by `(SID,
channel)`. Any other packet is matched by `(SID, channel, local specific ID)`, so its byte 17
must equal the receiver's own ID. Packets matching no connection are dropped. READ.

R29. Learning the remote ID. On a HEARTBIT from a peer whose advertised version is > 3, if the
remote ID is still unknown, the receiver learns it from byte 17, unless that value equals the
remembered previous remote ID, in which case it does not learn it. Once learned, a HEARTBIT
advertising a different ID is discarded. READ.

R30. An implementation MUST put its own ID in HEARTBIT, echo the received ID in HEARTBIT_ACK, and
put the learned remote ID in every other packet (0 before it is learned). READ (behaviour);
MUST is INFERRED. It SHOULD avoid reusing the ID of its previous connection on the same session.
INFERRED.

R31. Channel range: the usable IOTC channel range is 0..31. One RDT create path tolerates 32;
the cancel path and IOTC reject anything above 31. Implementations MUST use 0..31. READ
(inconsistency retained).

## Creation

There is no SYN and no stream-open message. Readiness and ID exchange are done with
HEARTBIT/HEARTBIT_ACK, after DTLS if the connection is secure. READ.

### State machine

`CREATING` and `ESTABLISHED` are explanatory names; the binaries use several flags, not one
state variable. READ.

| State | Event | Action | Next | Label |
|---|---|---|---|---|
| (none) | create call | Library must be initialized. Allocate slot, specific ID, queues and buffers. Transmit, read and ACK sequences `(0,0)`. RTO 500000 µs. | ALLOCATED | READ |
| ALLOCATED | - | Enable IOTC channel (app: ON; firmware: OFF then ON). | CHANNEL_ON | READ |
| CHANNEL_ON | no auth callbacks | Use plain IOTC read/write. Start receive and send workers. | CREATING | READ |
| CHANNEL_ON | auth callbacks present | Create secure context, register PSK callback, create secure channel, run DTLS connect (client) or accept (server). Start workers only after success. | CREATING | READ |
| CHANNEL_ON | plain data seen during DTLS | Free secure context, send NEED_DTLS (`71`), sleep 500 ms, fail with −10023. | FAILED | READ |
| CREATING | every >99 ms of send-loop time | Send HEARTBIT. | CREATING | READ |
| CREATING | HEARTBIT received | Queue HEARTBIT_ACK; learn remote ID (R29); record peer version. | CREATING | READ |
| CREATING | completion check (every 5 ms) | Peer IOTC protocol ≥ 6: done when both HEARTBIT and HEARTBIT_ACK have been received. Peer IOTC protocol < 6: done when the receive watchdog is nonzero. | ESTABLISHED | READ |
| CREATING | EXIT (`70`) received | Fail with remote-exit (−10016). | FAILED | READ |
| CREATING | NEED_DTLS (`71`) received by a plain creator | Fail with local-not-support-DTLS (−10024). | FAILED | READ |
| CREATING | timeout, local cancel, session error | Clean up (below). | FAILED | READ |
| CREATING | done | Set established, allow writes. Set pacing divisor from IOTC session mode (50 for mode 2, else 2; initial value 8). Initialize window bookkeeping from the initial window. | ESTABLISHED | READ |
| any pre-established | failure | Stop workers, destroy secure context, release slot, return the local or underlying error. | FAILED | READ |

The pacing divisor is local state fixed at creation; it is never sent on the wire. READ. That it
paces the send loop inside the congestion window is INFERRED from its use; the exact effect is
unresolved.

### Timeouts

R32. The create call takes a timeout in milliseconds. The heartbeat phase fails when the
accumulated polling time exceeds it; 0 means no limit for that phase. The same value bounds the
DTLS handshake separately; 0 becomes **60000 ms** there. The tunnel's 30000 ms therefore applies
to each phase, not to a combined deadline. READ.

R33. While creating, the poll loop calls the IOTC session status check, and the extended session
check initially and again after more than 1000 ms of polling. READ.

### Setup flow

Synthetic IDs: app allocates 7, device allocates 9. INFERRED example; the rules are READ.

```text
 App (client, ID 7)                               Device (server, ID 9)
   |  [secure only: DTLS handshake over IOTC datatype 1]  |
   |---- HEARTBIT      conn_id=7 ------------------------>|  learns remote=7
   |<--- HEARTBIT      conn_id=9 -------------------------|  learns remote=9
   |<--- HEARTBIT_ACK  conn_id=7 (echo) ------------------|
   |---- HEARTBIT_ACK  conn_id=9 (echo) ----------------->|
   |   both sides: HEARTBIT seen + HEARTBIT_ACK seen => ESTABLISHED
   |---- DATA seq=(0,0) conn_id=9 ----------------------->|
   |<--- DATA_ACK2 seq=(0,0) conn_id=7 -------------------|
```

R34. A stand-in endpoint MUST send HEARTBIT every ~100 ms while creating and MUST answer every
HEARTBIT with HEARTBIT_ACK, including after establishment. It MUST NOT send DATA before it
considers itself established. INFERRED from the READ creation rules.

### Keepalive and watchdog

R35. Once established, each side sends HEARTBIT when more than 999 ms of send-loop time has
accumulated (nominally once per second). READ.

R36. The receive watchdog is set to 120 by DATA, urgent DATA, HEARTBIT, HEARTBIT_ACK and the DATA
ACK forms (5 while a local destroy is in progress). It is decremented once per established
heartbeat interval. At zero the connection stops. Nominally this is 120 s (or 5 s) of silence
after the last qualifying packet, not an exact wall-clock deadline. READ.

## Close, abort and failure

Flags that matter: running/exited status of each worker (2/3), established, allow-write, local
and remote abort, local and remote exit, force-stop, destroy-in-progress, "FIN received" and "FIN
acknowledged". READ.

### Transition table

| Event | Action | Label |
|---|---|---|
| Local destroy, established | Set destroy-in-progress. Wait for an active writer (up to 50 × 100 ms). If workers run, writes are allowed and no remote abort: flush the pending partial packet, disable writes, append FIN. Wait for the send worker; force receive exit; wait for the receive worker; send QUIT; free secure channel; channel OFF; release slot. | READ |
| FIN received, not established | Ignored (no established FIN action). | READ |
| FIN received, established | Queue FIN_ACK, set end-of-data and "FIN received", force send stop. If our FIN was already acknowledged, drop remaining FIN and force receive exit. The exit path sends QUIT. | READ |
| FIN_ACK received | Remove FIN nodes, set "FIN acknowledged", stop the sender. If "FIN received" is also set, force receive exit. The exit path sends QUIT. | READ |
| QUIT received | Force send stop, remove queued FIN. The exit path may itself send QUIT. No QUIT retry. | READ |
| Local abort | Clear send and receive queues. If no remote abort was seen, send ABORT then QUIT directly. Disable writes, set local abort and stop, join workers, destroy secure context, channel OFF, release slot. No FIN, no wait for ABORT_ACK. Waits for an active writer up to 50 × 100 ms first. | READ |
| ABORT received | Queue ABORT_ACK, set remote abort, force stop. The stop can race the ACK queue; ABORT_ACK is not guaranteed to go out before QUIT. | READ |
| Local cancel of a pending create | Mark local exit; shut down the secure channel if in setup; send EXIT and QUIT. | READ |
| Watchdog zero, or transport failure | Stop workers. Later API calls report destroyed or the stored last error. No reason-coded reset packet exists. | READ |
| Global de-initialize | Mark de-initializing, abort every connection (retrying every 50 ms while abort reports −10006 or −10011, no cap), free shared resources. | READ |

### Graceful close flow

```text
 A (closing)                                   B
   |--- DATA ... (remaining queued data) ------->|
   |<-- DATA_ACK2 / DATA_SACK2 ------------------|
   |--- FIN seq=(FFFFFFFF,FFFFFFFF) tx=1 ------->|  end-of-data; reads drain, then −10009
   |<-- FIN_ACK (copied seq, tx=1) --------------|  B's send side stops
   |--- QUIT ----------------------------------->|  (A's exit path)
   |<-- QUIT ------------------------------------|  (B's exit path, may occur)
```

FIN is sent only after every earlier queued packet has been acknowledged (it must be the only
queued node). READ.

R37. A stand-in MUST answer FIN with FIN_ACK when established, MUST deliver all data received
before the FIN to its reader before reporting end-of-data, and SHOULD send QUIT when it stops.
INFERRED from READ behaviour.

R38. A peer MUST NOT depend on receiving ABORT_ACK or QUIT; both are best-effort. INFERRED.

### Receive-path errors

R39. Underlying receive errors −23, −22 and −14 end the receive worker; other nonpositive
results are retried after a 50 ms sleep. A nonpositive DATA send result stops the sender; a
negative one is stored as the last error and can be returned unchanged by later API calls.
READ. (These are IOTC / secure-channel codes; see the IOTC chapter.)

## Secure channel

R40. RDT itself applies no cipher, nonce, padding or MAC. A secure connection runs DTLS over the
IOTC session using the vendor secure-channel ("sCHL") API: create context, register a PSK
callback, create channel, set handshake timeout, then connect (client) or accept (server). The
RDT code selects no cipher-suite string, certificate or custom nonce. READ.

R41. PSK. Both sides derive the pre-shared key as the **32-byte raw SHA-256 digest** of the
password bytes, excluding the terminating NUL. No salt, iteration, username concatenation, hex
or Base64. READ. The client callback requires a nonempty identity and password; the server
callback receives the identity and asks its application for the password. READ. The app supplies
the account username as identity and the account password, from its remote-connect data. READ.
The PSK identity and handshake are DTLS fields, not RDT header fields. READ.

R42. Password length limits differ: Android app 3.3.2 accepts up to 1024 bytes, firmware 9.31 up to
**32** bytes. A client MUST NOT rely on passwords longer than 32 bytes working against the device.
READ (limits); MUST is INFERRED.

R43. Adapter. DTLS bytes are written with IOTC datatype **1** on the RDT channel. The reader uses
a 1388-byte buffer and 20 ms read slices; a packet arriving with datatype **0** is treated as
plain (non-DTLS) data, which triggers the NEED_DTLS path. The adapter enables IOTC partial
encryption and DTLS quiet shutdown. READ.

R44. DTLS retransmission: the app installs a timer callback giving 500000 µs initially and
doubling. The 64-bit firmware installs no callback and uses its TLS library default: 1000000 µs initially, doubling, capped at
60000000 µs, failing after 13 timeouts, all within the overall handshake timeout. READ.

R45. Plain/secure mismatch is a failure, not a fallback. A secure endpoint that sees plain data
sends NEED_DTLS and fails with −10023; a plain endpoint that receives NEED_DTLS fails with −10024.
READ.

R46. Predicted profile. With unmodified compiled defaults, PSK callbacks, no certificates and a
common EC group, the expected negotiation is DTLS 1.2 with
`TLS_ECDHE_PSK_WITH_CHACHA20_POLY1305_SHA256` (`0xCCAC`). The premaster secret is then
`BE16(len(Z)) || Z || BE16(32) || PSK` with `Z` the ECDHE shared secret, a 48-byte master secret,
12-byte IV XORed with `(zero4 || epoch2 || seq6)` as the record nonce, and a 16-byte tag. Not a
captured selection. INFERRED. Keys from the IOTC rendezvous layer never protect RDT packets.
INFERRED. Implementations SHOULD use a standard DTLS stack and keep one DTLS record per IOTC
datatype-1 packet. INFERRED. Full profile reasoning: [IOTC DTLS](../iotc/dtls.md).

DOC. DTLS 1.2 (RFC 6347) records have a 13-byte header (type, version `fe fd`, epoch, 48-bit
sequence, length, big-endian); DTLS does not make data reliable, and its record sequence is
independent of RDT's. RFC 4279 defines PSK identity and plain-PSK premaster construction.

## API error codes

These values are what the RDT API returns locally. None is sent on the wire. Names are the app's
declared constants; a declaration does not prove that this build emits every code. READ.

| Value | Name | Value | Name |
|---:|---|---:|---|
| 0 | `RDT_ER_NoERROR` | −10012 | `RDT_ER_CHANNEL_OCCUPIED` |
| −10000 | `RDT_ER_NOT_INITIALIZED` | −10013 | `RDT_ER_NO_PERMISSION` |
| −10001 | `RDT_ER_ALREADY_INITIALIZED` | −10014 | `RDT_ER_INVALID_ARG` |
| −10002 | `RDT_ER_EXCEED_MAX_CHANNEL` | −10015 | `RDT_ER_LOCAL_EXIT` |
| −10003 | `RDT_ER_MEM_INSUFF` | −10016 | `RDT_ER_REMOTE_EXIT` |
| −10004 | `RDT_ER_FAIL_CREATE_THREAD` | −10017 | `RDT_ER_SEND_BUFFER_FULL` |
| −10005 | `RDT_ER_FAIL_CREATE_MUTEX` | −10018 | `RDT_ER_UNCLOSED_CONNECTION_DETECTED` |
| −10006 | `RDT_ER_RDT_DESTROYED` | −10019 | `RDT_ER_DEINITIALIZING` |
| −10007 | `RDT_ER_TIMEOUT` | −10020 | `RDT_ER_FAIL_INITIALIZE_DTLS` |
| −10008 | `RDT_ER_INVALID_RDT_ID` | −10021 | `RDT_ER_CREATE_DTLS_FAIL` |
| −10009 | `RDT_ER_RCV_DATA_END` | −10022 | `RDT_ER_OPERATION_IS_INVALID` |
| −10010 | `RDT_ER_REMOTE_ABORT` | −10023 | `RDT_ER_REMOTE_NOT_SUPPORT_DTLS` |
| −10011 | `RDT_ER_LOCAL_ABORT` | −10024 | `RDT_ER_LOCAL_NOT_SUPPORT_DTLS` |

Paths seen: secure-context creation failure gives −10020; secure-channel construction failure
gives −10021; other underlying errors may pass through; destroy can report −10010 after cleanup.
READ.
