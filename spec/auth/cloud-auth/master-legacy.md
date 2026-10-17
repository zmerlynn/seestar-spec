# Cloud auth: master discovery and legacy authorization messages

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file covers how
the SDK finds its master servers, the legacy (unencrypted, transformed) packet header, the legacy
master query and device registration, and the other legacy authorization messages. The newer
encrypted record forms used by the Android SDK are in [master-record.md](master-record.md); relay
messages are in [relay.md](relay.md). Session rendezvous after authorization belongs to
[Kalay/IOTC session](../../transport/iotc/index.md).

Basis: static analysis of firmware 9.31 (device SDK 4.3.6, 64-bit build unless stated) and app
3.3.2 (client SDK 4.3.8). Firmware receive rows come from its main IOTC packet handler.

## Master host names

A master host name needs an installed licence (-1005 otherwise). READ. Inputs: a role, a region
and the licence realm.

| Role | Service label |
|---|---|
| Client (role 0) | `c-master` |
| Device (role 1) | `d-master` |
| First argument nonzero ("p2pod") | `p2pod-master` |

Other roles fail. READ. Region: the requested one if nonempty, else the stored one (default
`all`). If the licence `standalone` object has an entry for the region, that host name is used
as is. READ.

```abnf
master-host   = standalone-host / built-host
built-host    = region "-" service "-" realm [suffix]
                ; suffix is appended only when realm contains no "."
service       = "c-master" / "d-master" / "p2pod-master"
suffix        = iotc-suffix / p2pod-suffix / cn-suffix
                ; cn-suffix replaces the others when region is exactly "cn"
                ; iotc-suffix for c-master and d-master, p2pod-suffix for p2pod-master
```

READ. The three suffixes are fixed vendor domain names compiled into the SDK: one shared IOTC
platform domain, one domain for the p2pod service, and one domain for mainland China. They are
listed in [embedded-constants.md: Master host-name suffixes](embedded-constants.md#master-host-name-suffixes). No real
account realm was obtained.

Selecting p2pod. The app library has one call site, in its master-name resolver thread. It passes
a context word as the p2pod argument when a flag byte four bytes after it is zero, and 0
otherwise. READ (app library, 32-bit ARM build). No instruction in that library writes either
field by immediate offset; only reads were found, in the resolver and in a session check. READ
(search by offset). No block copy writes the field either; the only write that reaches it is the session-wide zeroing
when the context is set up, so the context word stays zero and the Seestar app always resolves
`c-master` names. READ (app library, SDK 4.3.8). On the device, the argument comes from a field of
the login context. The device uses the plain login, and SDK initialization clears the extended
login input (READ). The device reads this field without the flag check. Both device login calls
first zero the whole login context, and nothing else on the device writes the field, so the device
also always resolves `c-master` names. READ (64-bit build). The 32-bit build is the same: it reads the
field without the flag check, the session set-up zeroes it, and no store by offset or fixed-offset
block copy reaches it. READ (32-bit build). The two network worker routines that own a connection's
variable-length reads (the one that runs each accepted session, and the one that listens for new ones)
were checked on both builds: each contains exactly one variable-length copy, and each copies into a
buffer it has just allocated on the heap for that call, not into the login context; neither routine
ever forms the login context's address at all, fixed or computed. READ (both builds, firmware 9.31).
No licence member, region value or public API that selects p2pod was found. A Seestar client MAY
ignore `p2pod-master` and SHOULD build `c-master` names. INFERRED.

Confirmed unchanged in firmware 9.75, on both the 64-bit and 32-bit builds: the device still never
writes the p2pod flag field anywhere, so it still always resolves `c-master` names, matching
firmware 9.31 exactly. READ. The same two worker routines were re-checked on firmware 9.75 (32-bit):
same result, one variable-length copy each, into a freshly allocated heap buffer, with no reference
anywhere in either routine to the login context's (relocated) address. READ (32-bit, firmware 9.75).
No remaining unresolved write path to this field was found on either architecture or firmware
version.

R60. A client MUST build master names from the licence realm and MUST honour `standalone`
overrides. READ (behaviour), INFERRED (obligation).

### Resolution and caching

Both SDKs resolve IPv4 and IPv6 addresses and fill at most twelve master slots. Resolver failure
is -2; uninitialized SDK is -12. READ. Cache policy differs:

- Device SDK: reuses a matching nonempty cached name while less than 60 s have passed. READ (both
  firmware builds).
- Client SDK: re-resolves when the saved timestamp second is earlier than the current second, the
  cached name is empty, or the name differs. READ. In effect it re-resolves on almost every call
  (INFERRED).

### Ports

R61. Master UDP port is 10240. TCP master attempts cycle through ports 80, 443, 21047, 8080, 8000
across the twelve slots. Port 443 here is a plain TCP choice, not evidence of TLS. READ (TCP
port list: both SDKs; UDP port: client SDK).

## Legacy packet header

Legacy messages start with a 16-byte header (READ, device query/hello/register senders and the
client query sender):

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 0 | 2 | LE16 | Magic `0x0204` |
| 2 | 1 | u8 | Protocol version; `0x1d` in these senders |
| 3 | 1 | u8 | Flags: bit 1 set by the send wrapper; bit 0 selects a 64-byte transformed prefix |
| 4 | 2 | LE16 | Body length; packet length = 16 + this |
| 6 | 2 | — | Zero in the senders below |
| 8 | 2 | LE16 | Opcode |
| 10 | 2 | LE16 | Control constant (per message; `0x14` device, `0x18` query, `0x24` client, `0x3f` hello) |
| 12 | 4 | — | Zero in query, hello and register; reused by some messages (relay ID) |

R62. All header and body integers are little-endian on the wire. Embedded network addresses keep
network byte order for port and address. READ.

## Legacy transform

Before sending, the SDK sets header flag bit 1. If flag bit 0 was set, only the first 64 bytes
are transformed; otherwise the whole packet is. READ. The transform is a reversible permutation
with XOR; it is not encryption with integrity and adds no length.

**Mask.** Both SDKs build a fixed 32-byte ASCII phrase at initialization (reproduced in
[embedded-constants.md: Legacy transform phrase](embedded-constants.md#legacy-transform-phrase)). The first 16 bytes
are XORed with the licence `keyMask`; the last 16 are unused by the transform. The resulting 16
bytes are `mask`. READ. The iOS app 3.4.0 SDK stores the phrase as a plain literal rather than as two
XORed arrays (READ; bytes not repeated here).

**Full 16-byte blocks** of the transformed prefix, READ:

```text
for j in 0..3:  w[j] = ROR32(LE32(in[4j..4j+3]), R1[j]) XOR LE32(mask[4j..4j+3])
b = LE32(w[0]) || LE32(w[1]) || LE32(w[2]) || LE32(w[3])
for i in 0..15: c[i] = b[P[i]]
for j in 0..3:  out[4j..4j+3] = LE32(ROR32(LE32(c[4j..4j+3]), R2[j]))

R1 = [1, 5, 9, 13]      R2 = [3, 7, 11, 15]
P  = [11, 9, 8, 15, 13, 10, 12, 14, 2, 1, 5, 0, 6, 4, 7, 3]
```

**Final short block** of length `r` (< 16): XOR byte `i` with `mask[i]`, then permute: `r = 2`
uses `[1, 0]`; `r = 4` uses `[2, 3, 0, 1]`; `r = 8` uses `[7, 4, 3, 2, 1, 6, 5, 0]`; other lengths
keep the order. Bytes after the prefix are copied unchanged. READ.

**Reverse:** undo the second rotations (ROL), apply the same permutation (it is an involution),
XOR the mask, undo the first rotations. READ.

R63. P is its own inverse. READ. Implementers SHOULD test the transform against synthetic vectors
in both directions. The same transform, from the transport side, is described in
[IOTC framing: Scrambling](../../transport/iotc/framing.md#scrambling).

## Legacy master query

**`0x1007` query** (client and device SDKs; no RSA or AES wrapper). Body 38, control `0x18`,
total 54. READ.

| Offset | Size | Meaning |
|---:|---:|---|
| 16 | 20 | Target UID |
| 36 | 16 | Realm, fixed width (see [sdk-licence.md R43](sdk-licence.md#licence-json)) |
| 52 | 1 | Constant 6 |
| 53 | 1 | Role flag from the caller |

**`0x1008` reply** (device SDK). Accepted over UDP only from a known master address (TCP skips
that check). Body at least 56. READ.

| Offset | Size | Meaning |
|---:|---:|---|
| 16 | 20 | UID; must match the logged-in device or an active connection |
| 36 | 16 | unresolved (server-side) |
| 52 | 16 | Observed (NAT) address of the sender, passed to NAT tracking |
| 68 | 2 | unresolved (server-side) |
| 70 | 2 | LE16 TDU count |
| 72 | … | TDU sequence |

TDU format: u8 type, one unused byte, LE16 data length, data. Type 1: three LE16 values (VID,
PID, GID). Type 2: P2P server addresses, 16 bytes each, count = length / 16. Unknown types are
skipped. Each TDU is bounded against the message length. A matching reply updates device, group
and server caches and moves the query state 1 → 2. READ.

**`0x1009`** is an alternate-source NAT observation, not a second list. READ.

### Sixteen-byte server address entry

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 2 | Not used by the conversion |
| 2 | 2 | BE16 port |
| 4 | 4 | IPv4 address, network order |
| 8 | 8 | Not used by the conversion |

READ. The SDK's internal 20-byte address (byte 0 family: 0 IPv4, 1 IPv6; port at 2; address at
4–19) is a different structure and MUST NOT be confused with this wire entry. READ.

## Hello

**`0x8003` hello** to P2P servers, to learn protocol support. Body 8, control `0x3f`: LE32 hello
serial (incrementing) at 16, LE16 instance ID at 20, caller flag at 22 (1 when greeting a P2P
server), zero at 23. READ. Replies `0x8004` and `0x8005` are accepted with bodies of 16 or 24
bytes; the 24-byte form has the serial at 32 and the instance at 36 and updates server protocol
and NAT observations. The meaning of the first 16 reply-body bytes is unresolved (server-side).

## Legacy device registration

**`0x0120` register** (device). Body 117, control `0x14`, total 133 on the 64-bit build. READ.

| Offset | Size | Meaning |
|---:|---:|---|
| 16 | 20 | Device UID |
| 36 | 4 | LE32 TDU count = 2 |
| 40 | 4 | TDU header: type 1, zero, LE16 length 36 |
| 44 | 16 | Local network address |
| 60 | 4 | LE32 SDK version `0x04030603` |
| 64 | 4 | LE32 NAT type |
| 68 | 8 | IOTC auth key if the auth type is 0, else zero |
| 76 | 4 | LE32 timestamp (current seconds) |
| 80 | 4 | TDU header: type 2, zero, LE16 length = version string length + 1 |
| 84 | n | SDK version string plus NUL (49 bytes on the 64-bit build, 44 on the 32-bit build) |

**`0x0122` register-alive** is sent instead when the tracked local address and NAT are unchanged:
body 32, UID at 16, eight auth bytes at 36, timestamp at 44. If they changed, a full `0x0120` is
sent. READ.

Replies `0x0121` (body ≥ 28) and `0x0123` (body ≥ 40) need a known UDP P2P server source and a
matching UID; they update login status. The alive reply's address at 36 goes to NAT tracking and
its timestamp at 52 to liveness accounting. READ.

R64. A stand-in device MUST send the full register when its address or NAT type changes. READ
(behaviour).

## Other legacy authorization messages

Absolute offsets; each packet starts with the 16-byte header. "Minimum" is a receiver check.
READ (device SDK).

| Opcode | Direction | Body | Fields and behaviour |
|---|---|---:|---|
| `0x0008` unlicensed | master → client/device | ≥ 20 | UID at 16. Device: clears a login bit. Client: sets the unlicensed flag. UDP needs a known master |
| `0x000a` no TCP support | server → client/device | ≥ 20 | UID at 16; sets no-TCP flag |
| `0x0211` precheck 1 | client → P2P server | 20 | UID at 16; control `0x24` |
| `0x0214` precheck 2 | client → P2P server | 32 | UID at 16; zero 36–39; auth key[8] at 40 or zero; control `0x24` |
| `0x0212`, `0x0215`, `0x0216` precheck replies | P2P server → client | ≥ 44 (extended ≥ 48) | UID at 16; LE32 seconds at 36 (stored as ms); 40–51 unresolved (server-side); LE32 NAT at 52; LE32 API version at 56; extended: auth-use byte at 60 |
| `0x0227` device not logged in | P2P server → client | ≥ 20 | UID at 16; marks device not logged in |
| `0x0229` device asleep | P2P server → client | 24, or ≥ 28 | UID at 16; long form LE32 seconds at 40 (× 1000); short form otherwise unresolved (server-side) |
| `0x022e` authorization failed | P2P server → client | ≥ 24 | UID at 16; LE32 reason at 36, stored as an auth status byte |
| `0x0231` check device status | client → server | 28 | UID at 16; caller's eight bytes at 36; control `0x24` |
| `0x0232` status reply (TCP) | server → client | ≥ 28 | UID at 16; two LE32 words at 36, 40, saved in swapped order (see below); matching TCP server entry moves to state 24 |
| `0x0114` or `0x0118` device sleep notify | device → P2P server (built; transmission unresolved) | 24 | UID at 16; four more bytes at 32 from the same fixed source as the UID; LE32 caller value at 36 (only for input type 3, else zero); control `0x14` |
| `0x0124` register sleep | device → P2P server | 32 | UID at 16; auth[8] at 36 or zero; LE32 caller value at 44 (only for input type 3, else zero); control `0x14` |
| `0x0125` register sleep reply | P2P server → device | ≥ 20 | Matching UID; runs the sleep callback if the sender is IPv4 |
| `0x0126` notify register | P2P server → device | ≥ 20 | Matching UID; schedules a fresh registration |

`0x0114`/`0x0118` is a second, shorter device-originated message, built by the same routine
family as `0x0124` and sharing its control constant, its register-input-type-3 test and its
caller-value field (at a different offset, matching the shorter body). The opcode itself is the
only difference: `0x0118` when the register input type is 3, `0x0114` otherwise. Identical in both
builds and unchanged in firmware 9.75. READ (construction). It is built next to a register packet
in a device wake/retry routine distinct from the plain login path that builds `0x0124`; whether it
is actually sent on the wire, and to whom, was not confirmed in this pass. unresolved (transmission).

The last word of `0x0124` is logged as a sleep serial. The builder copies it from its caller's
argument only when the register input type is 3, and writes zero otherwise; it is set by the
device, not by the server. READ. Its unit and meaning are unresolved.
`0x0232` is a device-status check, not a separate credential exchange. READ. Of its two LE32
words, the app library's local device-status query consumes the first one (packet offset 36) as a
status bitfield, where bit 0 set means the device is reachable, and consumes the second (offset 40)
only to pick the most recently updated of several matching connection entries before testing the
first word — consistent with it being a sequence number or timestamp, though its absolute unit is
not recoverable from the client alone and still needs server evidence. READ (app library, SDK
4.3.8).

R65. A client MUST treat `0x0008` as a terminal licence failure for that attempt and `0x022e`
as an authorization failure. INFERRED (from the flags set and the API errors in
[state-timers.md: API error mapping](state-timers.md#api-error-mapping)).
