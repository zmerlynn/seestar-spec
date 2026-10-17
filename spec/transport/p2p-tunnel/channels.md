# P2P tunnel: channels, data forwarding and flow control

Part of the [P2P tunnel chapter](index.md). This file covers how one forwarded TCP
connection becomes a tunnel channel: listener and channel allocation, SETUP, DATA,
half-close and close, and PAUSE / RESUME / WAKE flow control. Frame layout and login are in
[framing.md](framing.md); session teardown and timers in [session.md](session.md).

Basis: static analysis of the app tunnel library (app 3.3.2) and firmware 9.31 (both builds),
which agree on everything here unless noted.

## Listeners and mappings

R28. A port mapping creates a local TCP listener on the Agent (backlog 20, a 256-entry
mapping table); it does not allocate a tunnel channel. Each accepted local TCP connection gets
its own channel. The normal remote address is <loopback> (the Server's loopback). READ.

R29. Removing a mapping closes its listener only. It does not close established channels or
send any frame. Removing mappings and disconnecting the session are separate operations.
READ.

## Channel allocation and reuse

R30. Each session has 256 channel slots. Slot state: 0 free, 1 active, 2 or more
quarantined. READ.

R31. Each listener remembers the last index it chose (initially 0) and scans
`(last + 1) mod 256` onward for 255 candidates, so its first choice is 1 and its last choice
is skipped in a scan. If none is free it holds the accepted socket, sleeps 500 ms and scans
again, with no retry cap. READ.

R32. Release sets the slot to 2. A once-per-second sweep, over active sessions only,
increments every slot state above 1 and sets it to 0 once it exceeds 30. READ. A released
index is therefore reusable after about 28 to 29 seconds plus scheduling delay; it is not a
fixed 30 s timer. INFERRED.

R33. Quarantine is local to the allocator. An incoming SETUP may overwrite a quarantined slot;
it is not a negotiated lease. READ. A client SHOULD NOT reuse a channel index soon after
releasing it, so that late frames for the old connection are not taken for the new one.
INFERRED.

## SETUP (`01`)

The Agent sends SETUP with the chosen channel index when it accepts a local TCP connection.

Current form, `L = 52`:

| Payload offset | Size | Type | Endianness | Meaning |
|---:|---:|---|---|---|
| 0 | 2 | u16 | little | Address family, 2 (IPv4); the receiver overwrites it with 2 |
| 2 | 2 | u16 | **big** | Remote TCP destination port |
| 4 | 4 | bytes | network order | IPv4 address; normally `7f 00 00 01` (<loopback>) |
| 8 | 8 | bytes | - | `sockaddr_in` padding, 0 |
| 16 | 33 | bytes | - | Service ID, at most 32 bytes plus NUL; empty for port mapping |
| 49 | 3 | bytes | - | 0 |

The first 16 bytes are an IPv4 `sockaddr_in` memory image. A legacy form with `L = 16`
(the `sockaddr_in` only) is also accepted. READ.

R34. A client MUST send the current 52-byte form with an empty service ID, the remote port
big-endian, and address <loopback>. INFERRED (from the app builder, READ). The Server does not
rewrite the address to loopback; it connects to the address given. READ.

R35. Server verification. READ:

- `L >= 52`, nonempty service ID: resolve the port through the service callback; no callback
  or a zero port rejects. The resolved port replaces the embedded port.
- `L >= 52`, empty service ID, nonzero port: run the port callback. Empty ID and zero port
  rejects.
- `L = 16`: run the port callback; a negative result rejects.
- Other lengths can fall through without verification in the native code. A new Server
  SHOULD reject them. INFERRED.

A rejection sends DATA_CLOSE with result 2.

Reserved bytes on receive (READ, device library, 64- and 32-bit builds): the `sockaddr_in`
padding (bytes 8–15) and the trailing bytes 49–51 are never read; the 16-byte image, with the
family overwritten, is passed to `connect`. The service ID is passed on as a C string starting at
byte 16, and only its first byte is tested (empty or not). The receiver does not bound the
string to 33 bytes or force a terminator; the message buffer is zero-filled beyond `L`, so an
unterminated ID runs into bytes 49–51 and then zeros. Bytes after the first NUL are not read.

R35a. A sender MUST NUL-terminate the service ID within its 33 bytes and SHOULD send zeros in
the padding, the tail of the service-ID field and bytes 49–51. A receiver MUST ignore those
bytes, MUST stop the service ID at the first NUL, and SHOULD reject an ID with no NUL in its 33
bytes. INFERRED (policy).

R36. After verification the Server: if the slot is active, shuts down and releases the old
socket; resets the slot; creates a TCP socket; marks the slot active; and connects
(blocking, no tunnel-level timeout or retry) to the given address. On socket or connect
failure it sends DATA_CLOSE with result 1 and releases the slot. On success it starts
forwarding. READ. Firmware 9.75 (64-bit, READ): unchanged. The 16-byte address image comes from the
client's SETUP body with only the family overwritten, the connect call uses it directly, and the
device's port callback returns "allowed" for every port, so no destination or port is restricted by
the tunnel server.

R37. There is **no positive SETUP acknowledgement**. The Agent MAY send DATA right after SETUP.
A failure is signalled only by a later DATA_CLOSE on that channel. READ.

R38. Quirk: a verification rejection sends DATA_CLOSE with the slot's stored index *before*
the slot takes the incoming index, so a never-used or reset slot can reject on a stale index
rather than the requested one. Connect failures use the correct index. READ. Because a
rejection can be lost this way, a client SHOULD close stalled channels by an explicit local
policy. INFERRED.

R39. If the Agent's SETUP write to RDT fails, it closes the accepted local socket before
activating the channel. READ.

## DATA, half-close and close

### DATA (`02`)

R40. A sender reads at most 8192 bytes from the local socket per frame and sends
`02 ch LE16(n) data[n]`. The bytes are opaque; TCP segment boundaries are not preserved.
READ.

R41. If an RDT write of a DATA frame fails, the whole frame is kept and retried before the
next local read; a nonnegative write is taken as complete. READ.

R42. A receiver drops DATA for an inactive slot, an invalid socket, or a channel whose local
write direction has ended; otherwise it queues the bytes for the local socket. READ.

R43. The native queue starts at 16 bytes or more and doubles as needed; the PAUSE threshold
`B` ([Pause, resume and wake](#pause-resume-and-wake)) is not a size cap. A queue-allocation failure is ignored and the bytes are
lost silently. The sender removes only bytes the local socket accepted and keeps the rest.
READ. A new implementation SHOULD bound its queue by local policy and close the channel on
overflow rather than drop bytes silently. INFERRED.

### State flags

Per channel: `R` = local TCP read has ended, `W` = local TCP write has ended, `E` = peer
DATA_END received and not yet acted on. All 0 when SETUP activates the slot. READ.

| Event | Action |
|---|---|
| Local `recv` returns 0, or fails other than `EINTR`/`EWOULDBLOCK` | Set R=1. If W=0 send `03 ch 00 00`. If W=1 send `04 ch 01 00 01` and release. |
| Receive `03` on an active channel | Set E=1. Keep draining queued data to the local socket. |
| Queue empty, E=1, R=0 | Set W=1, `shutdown(SHUT_WR)`; keep reading the local socket. |
| Queue empty, E=1, R=1 | Release; no frame sent. |
| Local `send` fails with `EINTR`/`EWOULDBLOCK` | Keep queued bytes; retry later. |
| Other local `send` failure, R=0 | Set W=1; later DATA is dropped; reverse reads continue. |
| Other local `send` failure, R=1 | Send DATA_CLOSE result 1; release. |
| Receive `04` on an active channel | `shutdown(SHUT_WR)` and release at once; no drain, no reply. |
| `03` or `04` on an inactive channel | Nothing. |

All READ.

R44. DATA_END is a TCP half-close: data already queued MUST be delivered before the local
write side is shut down, and the reverse direction stays open. DATA_CLOSE is an abortive
close: the receiver discards queued data. Neither is acknowledged. READ (native behaviour),
INFERRED (as a client rule).

### DATA_CLOSE (`04`) payload

| Payload offset | Size | Type | Meaning |
|---:|---:|---|---|
| 0 | 1 | u8 | Result: 1 = socket, connect or terminal I/O failure; 2 = SETUP verification failure |

R45. A receiver MUST accept `L = 0` and MUST release the channel whatever the result byte.
The result is diagnostic only. (The native diagnostic log reads the wrong byte, so device
logs are not a reliable source of close reasons.) READ.

### Release

R46. Release shuts down and closes the local socket (both directions), frees the queue, sets
R=W=1 and puts the slot in quarantine (state 2). Release itself sends no frame. LAN-direct
slots close both of their sockets. READ.

## Pause, resume and wake

### Variables

Per channel: `pause-request flag` (this endpoint has asked the peer to pause) and `local read state`
(a byte, the peer's control over this endpoint's local socket reads). Both 0 on reset. READ.

### Receiving

| Event | `local read state` |
|---|---|
| Receive PAUSE `05` | add 2 (a duplicate PAUSE still adds 2, with a warning) |
| Receive RESUME `06` | set 0 |
| Receive WAKE `07` (established) | set 2 |
| Building the socket-read set | include the socket only if `local read state < 3` and its read direction is open |
| About to read a selected socket | increment unless it is exactly 1 |
| `local read state` is exactly 3 when selected | skip the ordinary read |

All READ. Interpretation, INFERRED: 0 and 1 allow continuous reading; 2 allows one more read
and becomes 3; 3 stops reading until WAKE or RESUME. WAKE grants one more read opportunity
(up to 8192 bytes), not a byte credit. A PAUSE that arrives in state 0 also allows one last
read.

R47. A receiver of PAUSE MUST stop reading that channel's local socket, MAY complete at most
one further read, and MUST resume on RESUME. It MUST NOT treat PAUSE as an idempotent boolean
if it wants to match native timing. INFERRED.

### Sending

Let `B` be the buffer threshold: 512000 by default and in the app, 5120000 on the device.
High water is `B`, low water `floor(4B/5)` (409600 and 4096000). READ.

R48. After queueing DATA and after each nonnegative local send, compute
`Q = this channel's queued bytes + the endpoint's RDT receive-queue bytes` (a failed status
query counts 0). The RDT term is shared by all channels of the session. READ.

- `Q > high` and `pause-request flag = 0`: send PAUSE, set `pause-request flag = 1` even if the
  write failed.
- `Q < low` and `pause-request flag != 0`: send RESUME, clear `pause-request flag` even if the write
  failed.
- Equality triggers nothing.

R49. WAKE: the sender worker counts bytes sent across its scan; once the count exceeds 8196 and `Q >
low`, a channel with `pause-request flag != 0` MAY be sent `07 ch 00 00` and the count is reset.
WAKE does not clear `pause-request flag`. The worker runs on queue notification or every 100 ms.
READ.

R50. Separate from PAUSE, the socket reader throttles itself on the RDT send queue: above
3774873 bytes queued it sleeps 5 ms (modes 0/1) or 10 ms (mode 2) and rechecks; a pass that
writes nothing sleeps 100 ms. READ. (The mode is an RDT/IOTC setting; see [RDT](../rdt.md).)

### Backlog after PAUSE

R51. PAUSE affects only future local reads. Bytes already passed to RDT are still sent, and
RDT carries no receive credit. READ. On the device, the RDT send buffer limit is never set,
so an RDT write blocks only while more than 4 MiB is already queued (READ; the 32-bit build
matches (READ); indirect calls not checked).

R52. Each paused channel can still deliver one more read (up to 8196 stream bytes); unpaused
sibling channels keep sending, so PAUSE gives no session-wide bound. INFERRED. PAUSE can also
be lost: the counter byte is updated without a lock by both the socket reader and the PAUSE
handler, so a racing read can leave the channel readable. This is a statically feasible
interleaving, not a measured rate. READ (unlocked updates), INFERRED (effect).

R53. A client MUST therefore keep receiving after it sends PAUSE and SHOULD size its local
buffering per channel by its own high-water policy rather than rely on the peer stopping.
Budgets such as 6 MiB per channel or 8 MiB per session are engineering choices, not limits
proven by the evidence. INFERRED. A client sent live PAUSE and RESUME on two channels during
stored-image downloads (2026-10-13) without breaking the session, OBSERVED; the bytes and time
received after PAUSE were not measured, and PAUSE on a live image stream was not observed. The
real burst after PAUSE is unresolved.
