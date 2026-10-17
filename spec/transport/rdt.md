# RDT reliable data channel

This chapter covers RDT, the reliable, ordered byte stream that runs over one channel of an
existing Kalay/IOTC session, optionally inside a DTLS secure channel. Below it sits the IOTC
session layer ([Kalay/IOTC session](kalay-iotc-session.md), detail in [iotc/](iotc/index.md)), which carries
each RDT packet as one unreliable datagram. Above it sits the [P2P tunnel](p2p-tunnel.md), whose messages
travel inside one RDT stream.
RDT knows nothing about JSON, methods or tunnel messages.

App names: RDT streams carry the app's “Telescope Network” remote connection. Names are the English
strings of iOS app 3.4.0; links are READ (app call sites) unless marked.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind an
implementation of either endpoint (app side or a stand-in device). Sentences that say what "the
app" or "the device" does are descriptions.

Every claim carries a label (see `CONVENTIONS.md`):

- **READ**: seen by static analysis of the RDT library shipped in app 3.3.2 (32-bit ARM Android
  build, SDK 4.3.8 build 0) and linked into the firmware 9.31 imager (64-bit and 32-bit builds, SDK
  4.3.6 build 3). Both sides agree unless a difference is stated.
- **DOC**: taken from public vendor RDT documentation or an IETF RFC. It describes the general
  mechanism, not what a Seestar session selected.
- **OBSERVED**: seen on a device. No RDT-level claim in this chapter is OBSERVED.
- **INFERRED**: a consequence or interpretation, not seen directly.
- **unresolved**: not established either way.

No target code was executed and no device was contacted for this chapter.

Notation. All integers are unsigned unless stated. `LE` is little-endian. Message types are given in
hex (`02` is DATA). A sequence number is a pair `(low, high)` of 32-bit words. Names such as
`ackNext`, `lastContiguous` and `ESTABLISHED` are explanatory; they are not binary symbols.

## Overview

```text
+------------------------------------------------+
| P2P tunnel messages  (p2p-tunnel.md)           |
+------------------------------------------------+
| RDT: 20-byte header + payload, wire version 5  |  <- this chapter
+------------------------------------------------+
| optional DTLS (IOTC secure channel, datatype 1)|
+------------------------------------------------+
| IOTC session write/read on channel 0..31       |  (kalay-iotc-session.md)
+------------------------------------------------+
```

R1. RDT is carried one complete packet per IOTC write, with no extra length prefix, checksum or
MAC added by RDT. READ. Details: [framing](rdt/framing.md#packet-boundary).

R2. The RDT wire version is **5** in every packet constructor on both sides. It is unrelated to
the SDK versions (app 4.3.8 build 0, firmware 4.3.6 build 3). READ.

R3. Reliability is packet-based: each DATA packet has a 64-bit packet sequence (not a byte
offset), the receiver acknowledges with cumulative and selective ACKs, and the sender
retransmits on an RTO or on hole evidence. READ. Details: [reliability](rdt/reliability.md).

R4. There is no SYN. A connection is ready once both sides have exchanged HEARTBIT and
HEARTBIT_ACK (after the DTLS handshake, if secured). Closing uses FIN/FIN_ACK followed by QUIT;
ABORT is a hard stop. READ. Details: [session lifecycle](rdt/session.md).

### Use by the Seestar app

R5. The app reaches the device through the P2P tunnel. When the tunnel has an authentication
callback it creates a **secure** RDT connection on IOTC channel **0** with a 30000 ms create
timeout; otherwise it creates a plain one with the same channel and timeout. The device's session
handler makes the same choice, from its registered callbacks, as the server side. READ. The
tunnel's callback supplies the account username and password from the app's remote-connect
data. READ. No credential values are given here.

R6. An implementation interoperating with the app or device SHOULD use channel 0 for the tunnel's
RDT stream and SHOULD be prepared for the secure variant. INFERRED.

## Chapter map

| File | Contents |
|---|---|
| [rdt/framing.md](rdt/framing.md) | Packet boundary, 20-byte header, size limits, message catalogue, ACK constructors, DATA_SACK2 payload, decoding rules. |
| [rdt/session.md](rdt/session.md) | Connection identity (channel, specific ID), creation state machine, secure channel and PSK, close/abort/failure states, API error codes. |
| [rdt/reliability.md](rdt/reliability.md) | Sequence numbers, write/read stream semantics, ACK generation and processing, RTO, retransmission, timers, congestion window, backpressure. |
| [rdt/examples.md](rdt/examples.md) | Worked synthetic byte vectors and flows; appendix on validating against a live device. |

## App / firmware comparison

| Item | App | Firmware | Label |
|---|---|---|---|
| SDK version | 4.3.8 build 0 | 4.3.6 build 3 | READ |
| Header, wire version, catalogue | 20 bytes, version 5, 15 types | Same | READ |
| Sequence, ACK2/SACK2, RTT constants | As in [reliability](rdt/reliability.md) | Same | READ |
| Channel activation at create | Channel ON | Channel OFF, then ON | READ |
| Password maximum in auth callback | 1024 bytes | 32 bytes | READ |
| DTLS retransmit timer | callback: 500000 µs, doubling | 64-bit build: TLS library default, 1000000 µs initial, doubling, 60 s cap, fail after 13 timeouts; 32-bit build not traced | READ |
| Tunnel RDT channel / create timeout | 0 / 30000 ms | 0 / 30000 ms | READ |

Firmware 9.75 (app 3.4.0) carries the same RDT library with logging stripped and many functions
inlined (READ, 64-bit imager). Compared and unchanged: the data payload range check (100 to 1280
bytes, otherwise -10014), the data send routine with its 1388-byte packet buffer, the client and
server authentication routines (32-byte password limit) and the version-string and channel-count
functions. The 9.75 send path writes through the secure channel directly when the channel's secure
pointer is set. These immediates are present in both firmware 9.31 and 9.75, with no drift: 500000
in the channel-create routine; 8000000 in the send thread; 6500 and 1000000 in the dynamic-limit
routine; 1000 in the create routine, the send thread and the read routine; 80 in the send thread
(and in the create routine in 9.75); and 120 in the status checks and the receive thread. How each
constant is used was not traced, so their roles are unverified. READ (presence), unresolved (roles).

The roles of five constants are established: the retransmission-timeout calculator computes the RTO
from a round-trip sample, clamped between a 100 ms floor and an 8 s cap (the `8000000` immediate);
the internal RDT creation routine seeds a channel's initial RTO at `500000` µs when the channel is
created; the receive thread resets a per-channel watchdog counter to `120` (or to `5` when a destroy
flag is set) after each qualifying packet; and the dynamic-limit routine ceilings a recomputed
floating-point send limit at `6500`. All five immediates, the same comparison or conditional-select
logic around them, and the same destroy-flag short-circuit on the watchdog, are present in firmware
9.75 and in the 32-bit build of both firmware versions. READ (presence and role, both builds, both
firmware versions).

Four further timer rules are established. The heartbeat-send predicate and the heartbeat-countdown
predicate take a connection-state value and an elapsed-time value: the first returns elapsed > 99 ms
when the state is the "creating" value (zero) and elapsed > 999 ms otherwise; the second
additionally requires the state to equal the specific "established" value before the 999 ms form is
allowed to fire. The internal RDT creation routine substitutes a 60000 ms DTLS handshake timeout
when the caller passes zero. The receive thread’s plain (non-secure) read path always passes a
2560-byte buffer and a 200 ms timeout, and its retry path after a nonpositive read result calls
`usleep(50000)`. The send thread compares an elapsed-microsecond figure against 2000 and, when
exceeded, refreshes a stored time reference and calls the dynamic-limit routine. `RDT_Write`
compares a per-channel queued-byte count against 4 MiB (both builds) and, while over it, loops on an
`IOTC_Check_Session_Status` check and a 100000 µs (`0x186A0`) sleep before re-checking. All five are
present with the same logic in firmware 9.75 and in the 32-bit build of both firmware versions. READ
(presence and role, both builds, both firmware versions). The reliability constants not named above
(ACK aggregation, create polling, send-loop sleep, unsent-packet age, destroy and de-initialize
retry, NEED_DTLS grace), the selective-ACK builder and the heartbeat constructor were not
established for firmware 9.75 or the 32-bit build, so [reliability: Timers
summary](rdt/reliability.md#timers-summary) remains verified for firmware 9.31 only for those rows.
INFERRED (unchanged, probable); unresolved (roles, remaining rows).

The app package also contains a second, unused RDT library of the same version with the same 15
handled types; the app loads the other one. READ. The 32-bit firmware's linked TLS internals
were not independently reconstructed. READ (coverage note).

## Open questions

0. **Firmware 9.75 RDT constants.** The watchdog interval, the RTO floor/cap/initial value, the
   dynamic send-limit ceiling, the HEARTBIT while-creating/established split, the DTLS handshake
   timeout substitution, the plain receive call's buffer/timeout and retry sleep, the slow-write
   threshold, and the write-backpressure wait are now traced to their functions and confirmed
   unchanged in role across firmware 9.75 and the 32-bit build ([App / firmware comparison](#app--firmware-comparison)). The remaining values
   listed in [reliability](rdt/reliability.md) ([Timers summary](rdt/reliability.md#timers-summary) timers: ACK aggregation, create polling,
   send-loop sleep, unsent-packet age, destroy and de-initialize retry, NEED_DTLS grace) were not
   verified for firmware 9.75 or for the 32-bit build; the immediates are present unchanged in 9.75
   but their roles were not traced ([App / firmware comparison](#app--firmware-comparison)). unresolved (remaining timers).

1. **Negotiated DTLS profile.** The compiled defaults predict DTLS 1.2 with an ECDHE-PSK
   ChaCha20-Poly1305 suite (see [session: Secure channel](rdt/session.md#secure-channel)). The runtime
   provider configuration, ClientHello extensions, EC group and selected suite need passive
   handshake observation. INFERRED.
2. **FIN timing.** Practical close latency when FIN_ACK is lost: see
   [reliability R73](rdt/reliability.md#fin-retransmission). Implementations MUST NOT assume a
   "four RTO" rule. INFERRED.
3. **Connection reuse.** The one-byte specific ID and the remembered previous remote ID suggest
   stale-packet rejection across reconnects. Corner cases with delayed packets after repeated
   create/destroy are unresolved. The ID is not a cryptographic nonce. INFERRED.
4. **Nondefault tuning.** Environment overrides of the window, the stored but unused
   pending-ACK setting, clock jumps, sequence high-word wrap and unusual IOTC session modes were
   not exercised. INFERRED.
5. **Allocation and close races.** ACK generation runs before receive-queue allocation, and
   terminal control ACKs are queued while workers stop. Memory exhaustion or close races may
   break expectations formed from normal traffic. INFERRED.
6. **Malformed input.** The original receive path has no demonstrated full length/count
   checking. Acceptance of truncated or oversize packets is not an interoperability requirement;
   conformance tests SHOULD use valid frames only. INFERRED.
7. **Channel bound.** One RDT create path accepts channel 32, another rejects >31; IOTC itself
   rejects >31. The usable range is 0..31. READ (inconsistency retained).
