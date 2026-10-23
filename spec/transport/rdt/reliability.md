# RDT sequencing, acknowledgement and retransmission

Part of the [RDT chapter](../rdt.md). This file covers how the byte stream is cut into numbered
packets, how receivers acknowledge them, and how senders time retransmissions and size their
window. Packet layouts are in [framing](framing.md); connection setup and close in
[session](session.md). The stream carries [P2P tunnel](../p2p-tunnel.md) messages over an
[IOTC session](../kalay-iotc-session.md). Labels: [rdt.md: Conventions](../rdt.md#conventions).

Basis: static analysis of the RDT write, read, receive-thread, send-thread, RTO and window
routines in app 3.3.2 and firmware 9.31 (both builds). The constants are firmware 9.31 values; the
nominal constants and roles are traced unchanged in firmware 9.75 and the 32-bit build
([rdt.md: App / firmware comparison](../rdt.md#app--firmware-comparison)).

## Sequence numbers

R47. A sequence is the pair `(low, high)` of the header's two 32-bit words. Order is unsigned
lexicographic on `(high, low)`. It counts **packets**, not bytes. READ.

R48. The first DATA packet of a connection has `(0,0)`. Next-sequence rule: READ.

```text
next(low, high):
    if low < 0xF0000000: return (low + 1, high)
    else:                return (0, (high + 1) mod 2^32)
```

So `(0xF0000000, h)` is followed by `(0, h+1)`, never `(0xF0000001, h)`. There is no half-range
(serial-number) comparison and no special ordering at high-word wrap. READ. FIN's
`(FFFFFFFF, FFFFFFFF)` is a sentinel, not part of the sequence space. READ.

R49. An implementation MUST use exactly this successor rule for both sending and in-order
delivery; a plain 64-bit increment desynchronizes after `0xF0000000` packets. INFERRED.

R50. DATA and urgent DATA share one sequence space and one receive queue. READ.

## Writing

R51. Write fills a temporary payload buffer. Each time it holds a full packet (default 1280
bytes) the packet is assigned the next sequence and queued. A partial tail stays in the buffer.
Flush queues a nonempty tail and returns at once; it does not wait for acknowledgement. The send
worker also queues a pending tail on its own. READ. Hence writes may be delayed up to one send
loop (20 to 100 ms) unless flushed. INFERRED.

R52. A successful Write reports bytes accepted locally, not delivered. A retransmission reuses
the original sequence and payload unchanged. READ.

R53. Producer backpressure (local only, never on the wire): by default Write waits in 100 ms
steps while more than **4 MiB** (`0x400000` bytes) of payload is queued, checking connection and
IOTC status as it waits. With a positive configured limit, a write that would exceed it fails at
once with −10017. A limit of 0 disables the check. READ.

R54. Urgent write: flushes pending normal data, then packetizes the urgent bytes as type `10`.
Urgent packets skip the initial window gate ([Window and pacing](#window-and-pacing)) and are always eligible in a resend sweep.
Delivery is still in sequence order; urgent data is not out-of-band. READ. The API requires a
fixed private magic value as its first argument; it is a local API gate and not on the wire.
READ.

## Receiving and reading

R55. Per DATA or urgent DATA packet, the receiver first runs the ACK logic ([ACK generation](#ack-generation)), then inserts the
packet into the receive queue in ascending sequence order. Duplicates are dropped, as are
packets below the next sequence the application will read. READ.

R56. Read delivers only the packet whose sequence equals the next expected one, then advances
with the R48 rule. A partly consumed packet is kept so later reads may take any byte count.
Later packets never bypass a gap. READ. RDT is a byte stream: read boundaries need not match
write boundaries. DOC (vendor documentation) and READ.

R57. ACKs mean "received into the transport", not "read by the application". There is no
receive-window advertisement and no RDT-level receive byte cap. READ.

R58. Read returns as soon as any bytes are available. With none: timeout 0 returns −10007 at
once; a positive timeout polls in sleeps of `min(timeout, 50)` ms and returns −10007 once the
accumulated time exceeds it. A failed session check returns destroyed status. After FIN, once
queued data is exhausted, Read returns −10009. That code can be returned on the same call that
copied the last bytes, so a caller MUST treat −10009 as end-of-stream and MUST NOT assume every
byte was reported in a positive count on that call. READ (behaviour); MUST is INFERRED.

## ACK generation

R59. ACK policy by the peer's HEARTBIT-advertised version (R25): READ.

| Peer version | DATA (`02`) answered with | urgent DATA (`10`) answered with |
|---|---|---|
| ≤ 4 | DATA_ACK `42` per packet | `50` per packet |
| > 4 (5 today) | DATA_ACK2 `46` cumulative and DATA_SACK2 `45` selective | `50` per packet |

Both endpoints implement both policies. READ. A missing ACK never blocks receiving. READ.

### Version-5 receive state

R60. State (initially all zero): `ackNext` (next contiguous sequence expected), `lastContiguous`, a pending-cumulative counter, one pending selective run `[runStart,
runEnd]` with its header template, and a shared "last ACK sent" timestamp. The run is
separate from the sorted receive queue. READ.

R61. For each incoming DATA with sequence `S`: READ.

| Condition | Action |
|---|---|
| `S == ackNext` | Count pending cumulative progress; `lastContiguous = S`; advance `ackNext`. Then walk already-queued consecutive packets, advancing across a filled gap. Reconcile the pending run (last row). If at least 3000 µs (absolute difference) since the shared ACK timestamp, send ACK2. |
| `S < ackNext` (duplicate) | Send ACK2 at once; count pending cumulative progress again, so a later repeat ACK2 may follow. |
| `S > ackNext`, no run | Flush any pending ACK2; save run `[S,S]` and its template. No SACK2 sent yet. |
| `S == next(runEnd)` | Extend run to `S`. If ≥ 3000 µs since the shared ACK timestamp, send SACK2 and clear the run. |
| `S > ackNext`, run exists, not adjacent | Send SACK2 for the old run; start new run `[S,S]`. |
| Contiguous progress with a run pending | If `runEnd ≤ lastContiguous`, drop the run. Else if `runStart < lastContiguous`, set `runStart = lastContiguous`, then send the run. |

R62. Independently, the send worker flushes any pending ACK2 and SACK2 once its accumulated loop
time exceeds **99 ms**. So the 3 ms figure is an event-driven threshold, not a timer; the fallback
is about 100 ms. READ. ACK2 and SACK2 carry `lastContiguous` in the header sequence. READ.

R63. At startup, an out-of-order first DATA can produce a SACK2 whose header sequence is `(0,0)`
before packet 0 has arrived, because the watermark starts at zero. INFERRED. Senders MUST NOT
treat a SACK2 header sequence as a cumulative ACK (R66), which avoids the ambiguity. READ (the
originals do not).

R64. A stand-in receiver MAY use a simpler policy, such as an ACK2 per in-order packet and a
SACK2 per out-of-order packet, since senders act only on what each ACK states. INFERRED.

## ACK processing at the sender

R65. `42` and `50` delete only the queued packet whose sequence exactly equals the header
sequence. For peer version > 4, `42` also marks every earlier outstanding packet for forced
resend if not already marked; `50` does not. An ACK for a packet not in the queue changes
nothing. READ.

R66. ACK2 (`46`) deletes every queued packet with sequence ≤ the header sequence. SACK2 (`45`)
deletes only queued packets inside each inclusive payload range; packets below a range start
may be marked for forced resend; the walk stops past the range end. SACK2's header sequence is
not used to delete anything. READ.

R67. One RTT sample at most per ACK: from the exact cumulative boundary (ACK2) or exact range end
(SACK2) or exact packet (`42`/`50`). Interior packets give no samples. READ.

R68. After deleting packets, the handler may send more queued packets (not FIN), subject to the
saved-window/current-window and next-node checks. READ.

### RTT and RTO

R69. All RTO state is in microseconds. Initial RTO is **500000**. A sample is taken only from a
packet whose `tx_count` is less than 2, and is skipped if the wall clock went backwards. With `R =
now − lastSend`, integer arithmetic, divisions truncating: READ.

```text
if SRTT == 0:
    SRTT   = R
    RTTVAR = R >> 1
else:
    old    = SRTT
    SRTT   = (875*old + 125*R) / 1000
    RTTVAR = (750*RTTVAR + 250*abs(old - R)) / 1000
RTO = min(8000000, SRTT + max(100000, 4*RTTVAR))
```

So RTO is between 100 ms (plus SRTT) and 8 s. INFERRED.

## Retransmission

R70. Send sweep (each send-loop pass): consider up to `window` queued packets (one
packet if the window is 0 and the queue is nonempty). A packet is eligible when: READ

- time since its last successful send ≥ RTO (a packet whose last-send timestamp has a zero seconds component counts as 16000000 µs
  elapsed; a never-sent packet is the expected case, INFERRED); or
- its force-resend flag is 1; or
- it is urgent DATA.

FIN is skipped unless it is the only queued packet. A successful write records the send time
and changes force flag 1 to 2, so a later hole-marking pass does not re-mark it. READ.

R71. On the first loss event of a sweep the sender records the loss time and the packet's saved
window as `Wmax`, and recomputes the window ([Window and pacing](#window-and-pacing)). A sweep that retransmits doubles RTO once:
`RTO = min(8000000, 2*RTO)`. A single write taking more than 2000 µs also resets the window
reference time and recomputes. READ.

R72. No fixed retransmission count limit was found; the 8-bit `tx_count` wraps and is not a
cap. READ. INFERRED consequence: a connection ends by watchdog, transport error, close or abort. A nonpositive DATA send result stops the sender. READ.

### FIN retransmission

R73. When the sweep visits a FIN that is the only queued packet, it sets a FIN-in-flight flag and
stamps a FIN timestamp, before checking eligibility; this repeats on later sweeps. At the end of the
wait it compares `(now_us − finTimestamp_us) / 1000` (milliseconds) against `RTO_us <<
2` (microseconds × 4). READ. The units disagree and the timestamp keeps moving, so this is not a "4
× RTO" close rule; the practical effect is unresolved. With a fixed timestamp and RTO 500000 the
threshold would be 2000000 ms. INFERRED. In practice FIN is retransmitted like DATA on RTO, and the
watchdog, QUIT or the peer's FIN ends the connection. INFERRED.

R74. A stand-in SHOULD retransmit FIN on RTO and SHOULD give up after the watchdog interval
without FIN_ACK. INFERRED.

## Duplicate delivery (observed, firmware 9.75)

OBSERVED 2026-10-21 and 2026-10-22 (firmware 9.75, S50 Pro, bulk file copies of about 40 sub files through a local RDT stand-in): the share of received packets that arrived as duplicates (dropped by the receiver as already seen) was 3.4 to 7.4 percent on 2026-10-21 for uncapped reads at about 8 MB/s and 3 to 6 percent for copies overnight while the device was imaging. On 2026-10-22, with the device idle after the plan, eight copies gave 0.00 percent uncapped at 9.7 to 11.3 MB/s and 0.01 to 0.07 percent when read-rate capped at 1 to 3 MB/s. The read-rate cap therefore did not drive duplicates, and the number of parallel transfers did not scale them. INFERRED, unconfirmed: duplicates track device-side activity (imaging or processing), consistent with the sender's timer-driven individual resends described above; the device state during the 2026-10-21 window was not recorded.

## Window and pacing

R75. The window is local only. Defaults: initial **1000** packets, minimum **80**, ceiling
**6500**. Local environment overrides exist for the initial (positive integer) and minimum
(1..6499) values. The window is stored in 16 bits, so an initial override above 65535 truncates.
No window is advertised or negotiated, and there is no pause/resume message. READ.

R76. Window recomputation after a loss uses `Wmax` (16 bits), the microseconds elapsed since the
reference time, and an integer cube root. Normal-range arithmetic: READ.

```text
K        = floor(cuberoot(5 * Wmax))
delta_ms = trunc_toward_zero((elapsed_us - 100000*K) / 1000)
t        = delta_ms / 1000.0
target   = uint32_nonnegative_trunc(((t*t*t*1000.0)/1000.0) + Wmax)   # negative -> 0
q1       = queued_packet_count + 1
if target <= 6500:
    window = max(minimum, target)  if target <= q1  else  q1
else:
    window = min(6500, q1)
```

This is the binaries' own cubic curve, not a claim of TCP CUBIC compliance. The queue-limited
branch can give a window below the minimum. If the clock went backwards, the routine only resets
its reference time. READ.

R77. Initial send of a newly queued ordinary packet happens at once if the queue count before
appending is ≤ window and the old tail was the last packet sent; this can admit one packet more
than the window. Urgent DATA bypasses this gate; FIN is excluded. Other packets go out from the
send sweep or after ACK processing (R68). READ.

R78. A stand-in sender MAY use any congestion control that keeps the receiver's assumptions:
ordered sequences, retransmission with unchanged sequence and payload, and at most 1280-byte
payloads. INFERRED.

R79. A local "max pending ACK number" setting exists in the firmware API and is stored, but the
receive and send code never reads it; it does not change the ACK policy above. READ.

## Timers summary

| Timer / threshold | Value | Label |
|---|---|---|
| HEARTBIT while creating | send-loop time > 99 ms (≈100 ms) | READ |
| HEARTBIT established | > 999 ms (≈1 s) | READ |
| Watchdog | 120 intervals after last qualifying packet (5 during destroy) | READ |
| Send loop sleep | clamped 20..100 ms; 20 ms while creating. ACK draining sleeps up to 50 ms, or 5 ms after an ACK was sent | READ |
| Plain receive call | 2560-byte buffer, 200 ms timeout; 50 ms sleep after other nonpositive results | READ |
| ACK aggregation | 3000 µs event threshold; ≈100 ms send-loop flush | READ |
| Create polling | 5 ms; create timeout in ms, 0 = unbounded heartbeat phase | READ |
| DTLS handshake | create timeout, 0 → 60000 ms | READ |
| RTO | initial 500000 µs; 100 ms floor term; 8 s cap; ×2 per retransmitting sweep | READ |
| Unsent packet age | treated as 16000000 µs | READ |
| Slow write | > 2000 µs resets window reference | READ |
| Write backpressure wait | 100 ms per wait while > 4 MiB queued | READ |
| Destroy / abort waiting for writer | up to 50 × 100 ms = 5 s | READ |
| De-initialize abort retry | every 50 ms, no cap | READ |
| NEED_DTLS grace | 500 ms sleep after sending `71` | READ |

The watchdog and RTO rows above are traced to specific functions, each confirmed present with the
same role in firmware 9.75 and in the 32-bit build of both firmware versions (same immediates, same
comparison and conditional-select pattern): the receive thread resets a per-channel watchdog counter
to 120, or to 5 when a destroy flag is set, after each qualifying packet; a dedicated RTO routine
clamps a computed round-trip sample between a 100 ms floor and an 8 s cap; and the channel-create
routine seeds the initial RTO at 500000 µs. A separate routine recomputes a floating-point dynamic
send limit and ceilings it at 6500. READ.

Four further timer rules are unchanged in firmware 9.31 and 9.75, both builds: two small predicate
functions take a connection-state value and an elapsed-time value and decide whether to send, and
separately whether to count down, a heartbeat; the first returns elapsed > 99 ms when the state is
the "creating" value (zero) and elapsed > 999 ms otherwise, giving the HEARTBIT
while-creating/established split above; the second additionally requires the state to equal the
specific "established" value before it allows the count to proceed, so the 999 ms form only applies
once that exact state is reached. The channel-create routine takes a caller-supplied handshake
timeout and substitutes 60000 ms when the caller passed zero, giving the DTLS handshake row. The
plain (non-secure-channel) receive call always passes a 2560-byte buffer and a 200 ms timeout to the
underlying read primitive; a sibling secure-channel read call in the same thread takes the same
buffer size but no timeout argument. A `usleep(50000)` call sits in the receive thread's retry path
reached after a nonpositive read result, matching the "50 ms sleep" clause. The send thread computes
an elapsed microsecond figure from two stored timestamps and compares it against 2000; when
exceeded, it refreshes a stored time reference and calls the same dynamic-limit routine noted above,
matching the Slow write row. `RDT_Write` compares a per-channel queued-byte count against 4 MiB
(both builds) and, while over it, loops on an `IOTC_Check_Session_Status` check, an unlock, a 100000
µs (`0x186A0`) `usleep`, and a re-lock before re-checking, matching the Write backpressure wait row.
READ (presence and role, both builds, both firmware versions).

The other rows (send-loop sleep, ACK aggregation, create polling, unsent-packet age, destroy and
de-initialize retry, NEED_DTLS grace) are traced in firmware 9.31 and 9.75, both builds, with the same nominal constants and roles; see
[rdt.md: Open questions](../rdt.md#open-questions). READ. Clock-wrap, clock-jump and scheduling equivalence remain unresolved.
