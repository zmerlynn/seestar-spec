# Cloud auth: relay authorization and allocation

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file covers how a
client asks a P2P server to authorize and allocate a relay to a device, in the legacy form
(device SDK 4.3.6) and the record form (client SDK 4.3.8), the result codes, and server
alerts. Records and keys are defined in [master-record.md](master-record.md); headers in
[master-legacy.md](master-legacy.md). Relay data transport and hole punching belong to
[Kalay/IOTC session](../../transport/iotc/index.md).

Basis: static analysis of firmware 9.31 and app 3.3.2.

## What authorizes a relay

A relay request names the target UID and, optionally, an IOTC port and the eight-byte IOTC auth
key. The SDK uses the authenticated form when the port is nonzero **or** all eight key bytes are
alphanumeric. The tunnel username/password is never placed in that field. READ.

INFERRED: the relay authorization channel is the P2P-server control exchange below. No separate
HTTP relay login or TLS relay handshake was found. This is an evidence limit, not proof that none
exists.

"Random pair" (RID8) below means two 32-bit random-ID words copied by the senders without
derivation; their generation belongs to rendezvous. READ.

```
Client SDK                     P2P server                       Device SDK
   | relay request (UID, RID8,       |                                 |
   |  timeout, port, auth key) ----->|                                 |
   |<--------- result -7 (pending) --|-- relay knock (UID, RID8) ----->|
   |                                 |<- knock reply (result, RID8) ---|
   |<--------- result 0 (ready) -----|                                 |
   | session-info request ---------->|                                 |
   |<------- session info -----------|------- session info ----------->|
   | session-info ack (relay ID) --->|<------ session-info ack --------|
   |<====================== relayed IOTC session ======================>|
```

INFERRED (ordering of knock and results; the individual messages are READ).

## Legacy relay messages (device SDK)

Control `0x24` unless stated. Absolute offsets after the 16-byte header. READ.

| Opcode | Body | Layout |
|---|---:|---|
| `0x0205` relay request | 20 if peer protocol < 10, else 32 | UID[20] at 16; long form: RID8 at 36, LE32 timeout **60000** at 44 |
| `0x0207` relay request 3 | 36 | UID at 16; RID8 at 36; LE32 timeout **60** at 44; LE32 value **5** at 48 |
| `0x020a` relay request 4 | 48 | UID at 16; RID8 at 36 (zero if not yet set); LE32 timeout 60 at 44; LE32 value at 48 (0 or 5, by caller); LE16 IOTC port at 52; zero[2] at 54; auth[8] at 56 |
| `0x0209` session-info request | 20 if peer protocol < 10, else 44 | UID at 16; long form: RID8 at 36; LE32 flag (low byte) at 44; LE32 SDK `0x04030603` at 48; LE32 `0x1d` at 52; LE32 NAT at 56 |
| `0x0103` knock reply | 24 or 32 | UID at 16; LE32 result at 36; long form RID8 at 40; control `0x14` |
| `0x010c` newer knock reply | 32 | Same long layout; chosen by a caller flag |
| `0x030c` session-info ack | 28 | UID at 16; RID8 at 36; **LE16 relay ID in header bytes 12–13**, zero 14–15; control `0x14` device, `0x24` client |

R100. The two timeout values (60000 in `0x0205`, 60 in the newer forms) are distinct wire values.
A client MUST NOT send 60000 in the newer forms. READ (values); the server's meaning is unresolved (server-side).
The SDK's local relay deadline is 60 000 ms. READ.

**Replies the device SDK accepts** (READ):

- `0x0206`, `0x020b`: body 24–31 takes the old UID-only branch; body ≥ 32 takes the random-ID
  branch. `0x0208` always takes the random-ID branch and needs ≥ 32. Random-ID branch: UID at 16,
  signed LE32 result at 36, RID8 at 40. Over UDP the sender must be a known P2P server; the
  session must match and still be usable.
- `0x0103`, `0x010b` relay knocks (device side): old or new layout by size; UID must match; port
  acceptance and session capacity are checked; the device answers with a knock reply.
- `0x0303` relay session info: body 56–79 old form, ≥ 80 newer form. UID at 16, LE32 relay
  session ID at 36. Newer form: client address (16) at 40, device address (16) at 56, RID8 at 72,
  client/device SDK at 80/84, protocol at 88/92, and in the long form NAT at 96/100.

## Record relay messages (client SDK)

Sent in record type 4: four-byte clear P2P-server session ID, then the GCM-protected inner message.
Offsets below are relative to the inner header, after the session-ID prefix. Buffers are zeroed
first. READ.

| Opcode | Inner / body | Layout after header |
|---|---:|---|
| `0x020c` relay request record | 64 / 48 | UID at 16; RID8 at 36; LE32 timeout at 44 (60 from the UDP caller); LE32 value at 48 (5); LE16 port at 52; zero[2] at 54; auth[8] at 56 if valid, else zero. Control `0x24` |
| `0x0241` session-info request | 60 / 44 | UID at 16; RID8 at 36; LE32 flag at 44; LE32 SDK `0x04030800` at 48; LE32 `0x1d` at 52; LE32 local NAT at 56. Control `0x24` |
| `0x010e` knock reply record | 52 / 36 | UID at 16; LE32 result at 36; RID8 at 40; caller flag byte at 48; zero[3] at 49. Control `0x14` |
| `0x030f` session-info ack record | 44 / 28 | UID at 16; RID8 at 36; LE16 relay ID at header 12. Control `0x14` device / `0x24` client |
| `0x012a` register-sleep record | 48 / 32 | UID at 16; auth[8] at 36; LE32 caller value at 44. Control `0x14` |
| `0x0240` P2P request | 288 / 272 | UID at 16; four local addresses (16 each) at 36 (zero when local advertisement is disabled); RID8 at 100; LE32 NAT at 108; zero[160] at 112; eight bytes of optional IOTC auth material at 272 (copied without the alphanumeric check; not the tunnel password); zero[8] at 280; no inner nonce |
| `0x0806` connection-result record | 544 / 528 | Android app 3.3.2: offsets are relative to the inner header after the four-byte record-session prefix. UID[20] at 16; selected send-path storage slice[16] at 36; stored peer NAT byte at 52; live local NAT byte at 53; caller mode byte at 54; fixed client-OS value 3 at 55; LE32 error code at 56; copied session word at 60; LE32 SDK `0x04030800` at 64; copied session words at 68/72, the first logged as RandomID; copied local-network block[64] at 76; up to eight deduplicated NAT-address slices[16] at 140, unused slots zero; copied session blocks[64] at 268 and [128] at 332; zero[32] at 460; copied endpoint slices[16] at 492/508; optional caller IPv4 socket-address slice[16] at 524, otherwise zero; LE32 computed connect-time-ms at 540. Inner header: class tag `0x0204` at 0, byte `0x1d` at 2, LE16 body length 528 at 4, opcode `0x0806` at 8 and control `0x24` at 10; other unassigned header bytes remain zero. The inspected record-send path makes one conditional attempt per eligible server entry per invocation. READ for construction/call flow; complete copied-field meanings, successful transmission, server interpretation and firmware 9.31/9.75 or iOS app 3.4.0 telemetry parity remain unresolved. |

R101. `0x0241` flag at 44 is **1** for normal requests to the selected server (UDP and TCP) and
**0** for eligible unselected UDP servers and for the already-connected reply branch. READ.
The server's use of the flag is unresolved (server-side).

R102. TCP `0x0241` lifecycle: normal selection moves local TCP state 17 → 18 and marks one server
selected; while in 18 only selected servers are retransmitted. A retry is eligible when the
marker is zero or at least 2000 ms have accumulated. The stage timeout test (≥ 60 000 ms) is made
before adding the latest delta. READ. Full state contract:
[Kalay/IOTC session](../../transport/iotc/connect.md#udptcp-race).

**Record replies the client accepts in type 4** (exact lengths). The handler selects the server
context (UDP source guard), authenticates with the clear SID in the AAD, then compares the stored
SID. READ. Reply layouts MUST NOT be assumed to mirror the requests.

| Opcode | Inner / body | Layout |
|---|---:|---|
| `0x020d` relay request reply | 48 / 32 | UID at 16; signed LE32 result at 36; RID8 at 40; no nonce |
| `0x010d` relay knock | 52 / 36 | LE16 nonce at 16; opaque[2] at 18; UID at 20; RID8 at 40; LE16 IOTC port at 48; opaque[2] at 50. Checks nonce, UID, port, capacity; answered with `0x010e` |
| `0x030e` session info | 104 / 88 | UID at 16; LE32 relay ID at 36; client/device address at 40/56; RID8 at 72; client/device LE32 SDK at 80/84, protocol 88/92, NAT 96/100; no nonce; answered with `0x030f` |
| `0x030d` | 312 / 296 | LE16 nonce at 16; opaque[2] at 18; UID at 20; WAN address at 40; four LAN addresses at 56; RID8 at 120; client/device LE32 NAT at 128/132; eight WAN addresses (16 each) at 136; opaque[32] at 264; opaque[16] at 296 |
| `0x0129` notify-register | 40 / 24 | LE16 nonce at 16; opaque[2] at 18; UID at 20 |
| `0x012b` sleep ack | 40 / 24 | LE16 nonce at 16; opaque[2] at 18; UID at 20 |

Opaque fields are not invented server constants; a stand-in server MAY send zeros there only as a
guess. INFERRED.

## Relay result codes

Shared by the legacy random-ID reply handler (device SDK) and the record reply handler (client
SDK). READ.

| Result | Meaning |
|---:|---|
| 0 | Ready for relay |
| -1 | Device refuses (sets device-refusal flag) |
| -2 | Server refuses |
| -3 | No device with that UID |
| -4 | Another client is requesting relay |
| -5 | Device has no relay support on the server (sets no-relay flag) |
| -6 | Device logged in more than once |
| -7 | Request received; **pending** (neither success nor refusal) |
| -8 | Device may be asleep |
| -9 | IOTC port rejected (sets port-rejection flag) |
| -22 | Wrong auth key (auth status 2) |
| -23 | Old version; no authentication support |
| other | Logged as unsupported |

R103. A client MUST treat -7 as pending and keep the request alive, and MUST treat 0 as
permission to request session information. READ (behaviour). On 0 while already connected the
SDK requests session information again. READ.

A result outside the table is logged and sets no flag, state or callback: it is neither success
nor refusal, and the request task keeps running until its own lifetime ends (500 ms resend, 60000
ms lifetime; see [connect R9 and R11](../../transport/iotc/connect.md#udp-establishment)). READ
(client SDK). Whether servers send other values, and what they would mean, is unresolved (server-side). A client
SHOULD treat such a result as neither terminal nor success and let its ordinary deadline bound the
wait. INFERRED.

## Server alerts

Record type 14 uses the P2P server key/IV with the outer 12 bytes as AAD. Plaintext: LE32 server
session ID at 0, LE16 nonce at 4, alert byte at 6, record-type byte at 7, protocol version at 8.
Alert 1 is handled like `0x0227` (device not logged in); alert 2 like `0x0229` (device asleep).
READ.

The inspected handler has no nine-byte minimum check after decryption, may install the
authenticated SID into an empty slot before checking the nonce, and only logs the record-type
byte. READ.

R104. A receiver MUST require at least nine plaintext bytes and MUST validate SID and nonce before
changing state. INFERRED (policy stricter than the vendor handler).
