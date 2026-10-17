# RDT framing and message catalogue

Part of the [RDT chapter](../rdt.md). This file defines the RDT packet: how it sits on the
IOTC session ([Kalay/IOTC session](../kalay-iotc-session.md)), its 20-byte header, size limits,
and the 15 message types. Sequencing and ACK semantics are in
[reliability](reliability.md); setup and teardown in [session](session.md). Labels and
notation: [rdt.md: Conventions](../rdt.md#conventions).

Basis: static analysis of the RDT packet constructors and receive dispatchers in app 3.3.2 and
firmware 9.31 (both builds).

## Packet boundary

R7. A plain RDT connection writes one complete header plus payload with one IOTC session write
on its channel. A secure connection hands the same bytes to the IOTC secure channel (DTLS) as
one write. The receiver takes one IOTC packet, or one decrypted DTLS record payload, and
dispatches on its leading RDT header. READ.

R8. RDT adds no length prefix, checksum, MAC, compression, byte stuffing or padding of its own.
READ. (Protection supplied by IOTC or DTLS is outside RDT.)

R9. An implementation MAY expose the layer below as an unreliable, packet-preserving
`send(SID, channel, bytes)` / `receive(SID, channel)` interface and run the RDT state machine
on top. For secure RDT that boundary is decrypted DTLS application data; it SHOULD write exactly
one RDT packet per DTLS record. INFERRED. The native secure channel writes each RDT packet as
one DTLS record and reads back one record per packet; neither peer coalesces or splits RDT
packets at this boundary. READ; no capture confirms it.

## Header

All RDT packets start with this 20-byte header. Multi-byte fields are little-endian.

| Offset | Size | Type | Endian | Field | Meaning | Label |
|---:|---:|---|---|---|---|---|
| 0 | 4 | u32 | LE | magic | `0xF1C2975A`, on the wire `5a 97 c2 f1`. | READ |
| 4 | 1 | u8 | - | type | Message type, see [Message catalogue](#message-catalogue). | READ |
| 5 | 1 | u8 | - | version | RDT wire version, always emitted as `05`. | READ |
| 6 | 2 | u16 | LE | length | Payload byte count, excluding the 20-byte header. | READ |
| 8 | 4 | u32 | LE | seq_low | Sequence low word. Meaning depends on type. | READ |
| 12 | 4 | u32 | LE | seq_high | Sequence high word. | READ |
| 16 | 1 | u8 | - | tx_count | Transmission count, see R11. | READ |
| 17 | 1 | u8 | - | conn_id | Connection-specific ID, see R12. | READ |
| 18 | 2 | u16 | LE | reserved | Zero in fresh packets; copied in ACKs. Never interpreted. | READ |
| 20 | `length` | bytes | - | payload | Present only for DATA, urgent DATA and DATA_SACK2. | READ |

```text
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+---------------------------------------------------------------+
|                 magic 0xF1C2975A (LE)                         |
+---------------+---------------+-------------------------------+
|     type      |  version (5)  |        length (LE)            |
+---------------+---------------+-------------------------------+
|                      seq_low (LE)                             |
+---------------------------------------------------------------+
|                      seq_high (LE)                            |
+---------------+---------------+-------------------------------+
|   tx_count    |    conn_id    |        reserved (LE)          |
+---------------+---------------+-------------------------------+
|                    payload (length bytes) ...                 |
```

R10. A sender MUST emit the magic and version 5 as above, and MUST set `length` to the exact
payload size. READ (emitted values); MUST is INFERRED for interoperability.

R11. `tx_count`: a queued DATA, urgent DATA or FIN packet has the count incremented before each
send attempt, so the first transmission carries 1. Raw control packets (HEARTBIT, QUIT, ABORT,
EXIT, NEED_DTLS) carry 0. Single ACKs copy the count of the packet they acknowledge; ACK2 and
SACK2 copy it from their saved header template (the DATA packet that started the pending run).
The counter is 8 bits and wraps; it is not a retry limit. READ. The count also gates RTT sampling
(see [reliability: RTT and RTO](reliability.md#rtt-and-rto)).

R12. `conn_id`: HEARTBIT carries the sender's own ID; HEARTBIT_ACK echoes the ID it received.
Every other packet carries the learned **remote** ID, which is 0 until learned. READ. Lookup
rules are in [session: Connection identity](session.md#connection-identity).

R13. Bytes 18-19 are not a receive window. No RDT code reads them for flow control. Fresh packets
carry zero. READ. A sender SHOULD send zero and a receiver MUST ignore them. INFERRED.

R14. The local congestion window snapshot, timestamps, queue pointers and resend flags live in
local queue state only; they are not header fields. READ.

## Size limits

R15. Default maximum DATA payload is **1280** bytes. The local setting accepts 100 to 1280
inclusive. Normal packetization therefore emits at most **1300** RDT bytes per packet, before
DTLS or IOTC overhead. READ.

R16. The largest packet that is not DATA is DATA_SACK2 at 92 bytes. READ. The receive buffer is
2560 bytes; this does not establish support for larger DATA payloads. READ.

R17. The urgent-write API copies the caller's buffer without the normal segmentation loop. A
sender SHOULD keep urgent DATA within the 1280-byte limit. INFERRED.

## Message catalogue

The 15 types below are every distinct case handled by the app and firmware receive dispatchers
and every type the constructors emit. Both endpoints send and accept all of them; the creation
role (client/server) does not change layouts. Any other type value, including `44`, takes the
unknown-message path and has no RDT effect. READ.

| Type | Name | Payload | seq field | Purpose and receiver action | Label |
|---:|---|---|---|---|---|
| `01` | HEARTBIT | none | `(0,0)` | Setup and keepalive. Records peer version and "heartbeat seen", resets watchdog, queues `41`. | READ |
| `41` | HEARTBIT_ACK | none | copied | Echoes the advertised ID. Sets "heartbeat ACK seen", resets watchdog. | READ |
| `02` | DATA | stream bytes | packet seq | Stream data. ACK form depends on the peer's advertised version. | READ |
| `42` | DATA_ACK | none | acked seq | Deletes exactly that outstanding packet. For peer version > 4 also marks earlier outstanding packets for forced resend. | READ |
| `10` | urgent DATA | stream bytes | packet seq (shared with DATA) | Bypasses initial send gating. Receiver inserts as DATA, replies `50` (even at version 5). | READ |
| `50` | urgent DATA ACK | none | acked seq | Deletes exactly that packet. No forced-resend marking. | READ |
| `45` | DATA_SACK2 | 72 bytes | last contiguous | Selective ACK of inclusive ranges in the payload. Header seq is not applied cumulatively. | READ |
| `46` | DATA_ACK2 | none | last contiguous | Cumulative ACK: deletes all outstanding packets up to and including seq. | READ |
| `03` | FIN | none | `(FFFFFFFF,FFFFFFFF)` | End of outgoing data. Queued behind data; sent only when it is the only queued item. Established receiver marks end-of-data, queues `43`, starts stopping. | READ |
| `43` | FIN_ACK | none | copied | Removes queued FIN, records "FIN acknowledged", stops the sender. | READ |
| `04` | QUIT | none | `(0,0)` | Unreliable termination notice. Removes queued FIN, forces stop. No reply. | READ |
| `20` | ABORT | none | `(0,0)` | Hard abort. Receiver queues `60`, records remote abort, stops. | READ |
| `60` | ABORT_ACK | none | copied | Removes queued ABORT, forces receive shutdown. The aborting side does not wait for it. | READ |
| `70` | EXIT | none | `(0,0)` | Cancels a creation in progress; receiver fails creation with remote-exit. | READ |
| `71` | NEED_DTLS | none | `(0,0)` | Secure side detected a plain peer; receiver fails creation with local-not-support-DTLS. | READ |

The names HEARTBIT, DATA, FIN, QUIT, ABORT, DATA_ACK, DATA_SACK2 and DATA_ACK2 appear in the
binaries' log strings; the others are descriptive. READ.

### ACK constructors

R18. The ACK pairs are `01→41`, `02→42`, `03→43`, `10→50`, `20→60`. Each ACK is built from the
received header: magic, sequence, `tx_count` and bytes 18-19 are kept; type is replaced; version
is set to 5; length is set to 0. Byte 17 is replaced by the learned remote ID, except in `41`,
which keeps the received (advertised) ID. READ.

R19. ACKs go to a separate ACK queue, not the reliable send queue. They are sent once and freed
even if the write fails. There is no ACK of an ACK; a repeated DATA or HEARTBIT simply provokes
another ACK. READ.

R20. ACK2 (`46`) and SACK2 (`45`) are built from a saved DATA header template (see
[reliability: ACK generation](reliability.md#ack-generation)), not as a direct reply to one packet. READ.

### DATA_SACK2 payload

`length` is always `0x0048` (72) and the packet is always 92 bytes, even with one range. READ.

| Absolute offset | Size | Type | Endian | Meaning | Label |
|---:|---:|---|---|---|---|
| 20 | 4 | u32 | LE | Zero. Not read by the receiver. | READ |
| 24 | 4 | s32 | LE | Range count. Emitted as 1. Receiver acts only if the signed value is positive. | READ |
| 28 | 4 | u32 | LE | Range 1 start, low word. | READ |
| 32 | 4 | u32 | LE | Range 1 start, high word. | READ |
| 36 | 4 | u32 | LE | Range 1 end, low word. | READ |
| 40 | 4 | u32 | LE | Range 1 end, high word. | READ |
| 44 | 48 | - | - | Zero. Room for three more 16-byte range entries. | READ |

R21. Ranges are **inclusive** `[start, end]` and compare as sequence pairs (high word first).
The receiver steps through entries 16 bytes apart, `count` times. Header bytes 8-15 carry the
receiver's last contiguous sequence, not the range end. READ.

R22. A sender MUST emit exactly one range, the fixed 72-byte payload, and zero in unused bytes,
to match the originals. INFERRED (all emitted SACK2 have this form, READ). A receiver SHOULD
accept a count of 1 to 4. INFERRED.

### Decoding rules for new implementations

R23. A new implementation SHOULD drop, without reply: packets shorter than 20 bytes; packets with
the wrong magic; packets whose `length` exceeds the bytes received; SACK2 with a count above 4 or
above what the payload holds; and SACK2 ranges with start after end. INFERRED. These are
defensive rules, not behaviour shown in the originals. A stand-in MUST NOT rely on the original
peers performing such checks.

"What the payload holds" means `8 + 16 × count ≤ length`: the range array starts 8 bytes into the
payload. A count of zero or below is ignored, as in the originals. INFERRED. The original receiver
steps through `count` entries without a length or four-entry check. READ. Only the 72-byte payload
size is established as emitted; no other payload size has been seen from a peer.

R24. An unknown type MUST be ignored: no reply and no state change. The originals send no reply
and perform no RDT operation for it. READ; MUST is INFERRED.

R25. The version byte of DATA is not used to choose the ACK policy; only the version advertised
in HEARTBIT is. READ.
