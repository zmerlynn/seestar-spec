# RDT worked examples

Part of the [RDT chapter](../rdt.md). Synthetic byte vectors and flows for checking an encoder,
decoder or state machine offline, plus a non-normative appendix on validation against a device.
Layouts: [framing](framing.md); rules: [reliability](reliability.md), [session](session.md).
The layer below is the [IOTC session](../kalay-iotc-session.md); above is the
[P2P tunnel](../p2p-tunnel.md).

All vectors are **INFERRED**: constructed from the READ layouts, not captured. Endpoint A has
specific ID 7, endpoint B has ID 9; payloads and sequences are arbitrary test inputs. Bytes are
hex, 16 per line, offset 0 first. A live comparison is still required.

## Header vectors

### HEARTBIT from A (advertises own ID 7)

```text
5a 97 c2 f1 01 05 00 00 00 00 00 00 00 00 00 00
00 07 00 00
```

Type `01`, version 5, length 0, seq `(0,0)`, `tx_count` 0 (raw control), byte 17 = 7.

### HEARTBIT_ACK from B (echoes 7)

```text
5a 97 c2 f1 41 05 00 00 00 00 00 00 00 00 00 00
00 07 00 00
```

Byte 17 keeps the received ID 7 (the only ACK that does not substitute the remote ID).

### DATA from A, seq 0, first transmission, payload "abc"

```text
5a 97 c2 f1 02 05 03 00 00 00 00 00 00 00 00 00
01 09 00 00 61 62 63
```

23 bytes. Length `03 00`; `tx_count` 1; byte 17 = B's ID 9.

### Same packet, retransmitted

```text
5a 97 c2 f1 02 05 03 00 00 00 00 00 00 00 00 00
02 09 00 00 61 62 63
```

Only `tx_count` changes (2). An ACK of this copy gives no RTT sample (R69).

### DATA_ACK from B for seq 0 (version ≤ 4 peer policy)

```text
5a 97 c2 f1 42 05 00 00 00 00 00 00 00 00 00 00
01 07 00 00
```

Copies seq and `tx_count` 1; byte 17 becomes A's ID 7.

### DATA_ACK2 from B, cumulative through seq 2

```text
5a 97 c2 f1 46 05 00 00 02 00 00 00 00 00 00 00
01 07 00 00
```

### DATA_SACK2 from B: range [3,5], watermark 0

```text
5a 97 c2 f1 45 05 48 00 00 00 00 00 00 00 00 00
01 07 00 00 00 00 00 00 01 00 00 00 03 00 00 00
00 00 00 00 05 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00
```

92 bytes: header (length `48 00` = 72), zero word, count 1, start `(3,0)`, end `(5,0)`, 48
zero bytes. The header seq `(0,0)` is the watermark and MUST NOT release packet 0 (R66).

### FIN from A, first send / FIN_ACK from B

```text
5a 97 c2 f1 03 05 00 00 ff ff ff ff ff ff ff ff
01 09 00 00
```

```text
5a 97 c2 f1 43 05 00 00 ff ff ff ff ff ff ff ff
01 07 00 00
```

### QUIT and ABORT from A

```text
5a 97 c2 f1 04 05 00 00 00 00 00 00 00 00 00 00
00 09 00 00
```

```text
5a 97 c2 f1 20 05 00 00 00 00 00 00 00 00 00 00
00 09 00 00
```

### NEED_DTLS before any remote ID is known

```text
5a 97 c2 f1 71 05 00 00 00 00 00 00 00 00 00 00
00 00 00 00
```

Byte 17 is 0, so the receiver looks it up by `(SID, channel)` only (R28).

## Sequence rollover

The packet with seq `(0xF0000000, 0)`, then its successor `(0, 1)`:

```text
5a 97 c2 f1 02 05 01 00 00 00 00 f0 00 00 00 00
01 09 00 00 78
```

```text
5a 97 c2 f1 02 05 01 00 00 00 00 00 01 00 00 00
01 09 00 00 79
```

A receiver whose next expected seq is `(0xF0000000, 0)` delivers "x" then "y". A receiver using
a plain 64-bit increment would wait for `(0xF0000001, 0)` forever (R49).

## Version-5 ACK flow with one loss

A sends DATA 0..5; packet 2 is lost. ACK timing is illustrative: real timing may merge or delay
ACKs by up to ~100 ms (R62).

```text
 A                                                   B  (ackNext, lastContiguous, run)
 |-- DATA 0 -------------------------------------->|  (1, 0, -)
 |-- DATA 1 -------------------------------------->|  (2, 1, -)
 |<-------------------------------- ACK2 seq=1 ----|      A deletes 0,1
 |-- DATA 2 ---X  (lost)                           |
 |-- DATA 3 -------------------------------------->|  (2, 1, [3,3])  pending ACK flushed, no SACK yet
 |-- DATA 4 -------------------------------------->|  (2, 1, [3,4])
 |-- DATA 5 -------------------------------------->|  (2, 1, [3,5])
 |<--------------- SACK2 seq=1 range [3,5] --------|      A deletes 3,4,5; marks 2 for forced resend
 |-- DATA 2 (tx_count 2) ------------------------->|  (6, 5, -)  gap filled; walks 3..5
 |<-------------------------------- ACK2 seq=5 ----|      A deletes 2; no RTT sample (boundary 5 already gone)
```

Sender queue after each ACK: `{0..5}` → `{2..5}` → `{2}` (2 flagged) → `{}`.

## RTO arithmetic

Integer arithmetic per R69, starting from RTO 500000 µs:

| Sample R (µs) | SRTT | RTTVAR | RTO |
|---:|---:|---:|---:|
| 80000 (first) | 80000 | 40000 | 80000 + max(100000, 160000) = 240000 |
| 120000 | (875·80000 + 125·120000)/1000 = 85000 | (750·40000 + 250·40000)/1000 = 40000 | 245000 |
| 300000 | 111875 | 83750 | 111875 + 335000 = 446875 |

A sweep that then retransmits doubles RTO to 893750; a further one to 1787500, and so on up to
8000000.

## Window arithmetic

Per R76 with `Wmax` = 1000, minimum 80: `5·Wmax` = 5000, `K` = 17 (17³ = 4913 ≤ 5000 < 18³).

| elapsed_us | delta_ms | target | queued | window |
|---:|---:|---:|---:|---|
| 0 | −1700 | 995 | 2000 | 995 (target ≤ q1, ≥ minimum) |
| 2000000 | 300 | 1000 | 2000 | 1000 |
| 10000000 | 8300 | 1571 | 2000 | 1571 |
| 10000000 | 8300 | 1571 | 50 | 51 (queue-limited, q1) |
| 30000000 | 28300 | 23665 | 9000 | 6500 (ceiling) |

## Close and abort sequences

Graceful close initiated by A after B has acknowledged all data:

```text
 A                                            B
 |-- FIN  (seq FF.., tx 1, id 9) ----------->|  B: end-of-data, stop sending
 |<- FIN_ACK (seq FF.., tx 1, id 7) ---------|
 |-- QUIT (id 9) --------------------------->|  A's exit path
 |<- QUIT (id 7) ----------------------------|  B's exit path (may occur)
```

Abort by A: A sends ABORT then QUIT immediately and tears down without waiting. B may answer
ABORT_ACK, which A may never process. Both report abort errors locally (−10011 at A, −10010 at
B). READ (rules); flow INFERRED.

## Appendix: Validating against a live device (non-normative)

All steps INFERRED proposals.

1. **Passive baseline.** On an owner-authorized device, record app and firmware versions,
   network topology and time. Capture a normal connect, a modest transfer, an idle period and a
   disconnect. Keep account identifiers and secrets out of shared material.
2. **Layering.** Find the IOTC session/channel boundary using the IOTC chapter. Note DTLS
   (datatype 1) handshake records and their public version/suite choices. Ciphertext does not
   reveal RDT headers; if authorized, instrument the official IOTC/secure-channel API boundary
   instead of guessing from ciphertext.
3. **Header and setup.** At the plaintext boundary check magic, LE length, version 5, the
   HEARTBIT ID advertisement and echo, then DATA destination IDs. Check that both heartbeat
   conditions complete before application data. Record unknown types without naming them.
4. **Reliability, passively.** Correlate DATA sequences and `tx_count` with ACK2 and inclusive
   SACK2 ranges. Compare RTT/RTO changes, heartbeat spacing and partial-write packetization with
   the timers in [reliability: Timers summary](reliability.md#timers-summary).
5. **Simulator first.** Replay valid plaintext frames into an independent state-machine
   simulator: gaps, duplicates, reordering, rollover at `0xF0000000`, dropped ACKs, urgent DATA
   ordering, FIN/QUIT/ABORT and stale IDs.
6. **Controlled active phase.** Only after the baseline agrees, on a disposable authorized
   session with small transfers, delay or drop one DATA packet, then a cumulative ACK, then
   FIN_ACK. Keep the telescope otherwise idle. Do not fuzz malformed lengths or counts on an
   operational device.
7. **Recording.** Keep sanitized offset/timing tables and pass/fail per claim. Record any
   result as OBSERVED with its date; do not relabel READ or INFERRED claims.
