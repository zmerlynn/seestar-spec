# IOTC encrypted rendezvous records

Part of [Kalay/IOTC session](index.md). This file specifies the newer 12-byte record envelope the
app library uses to talk to master and P2P servers: record types, AES-GCM and RSA protection,
inner control layouts, acceptance rules, and the GCM key/IV cache. Below: UDP or TCP to servers.
Above: session setup ([connect.md](connect.md)). Peer data never uses these records
([framing: Data, alive and close packets](framing.md#data-alive-and-close-packets)). Server-side key agreement and relay
authorization context: [cloud-auth](../../auth/cloud-auth.md). Labels: [index: Conventions](index.md#conventions).

Basis: static analysis of the app library (app 3.3.2). The device library (firmware 9.31) has no
receive branch for this envelope. No server binary was available, so server behaviour is described
only as far as the client parses it.

## Envelope

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 0 | 4 | LE32 | Magic `0x0000cc51` (bytes `51 cc 00 00`) |
| 4 | 1 | u8 | Record version, generated 2 |
| 5 | 1 | u8 | Record type |
| 6 | 2 | LE16 | Body length |
| 8 | 4 | LE32 | Record SID; `0x0000ffff` is the global device-login context |
| 12 | var | | Body |

R1. The receiver requires total length 12..1416 and exact agreement with the body length. Over TCP
it can wait for remaining bytes. Client-role contexts reject the global `ffff` SID. READ.

R2. Modern records MUST NOT be sent to the device library's legacy peer dispatcher. INFERRED
(it has no branch for them, READ).

## Record types

The receiver processes types 1, 3, 4, 5 and 14; type 2 received is reported unsupported. READ.
Any other received type, including 6 to 13 and anything above 14, is logged and the record is
dropped with an error and no state change; the envelope length has already been checked
([R1](#envelope)). READ (app library). The app library's record dispatcher (reached through
`IOTC_Device_Listen_By_Nebula`) discards the record handler's return value for every record, clears
its diagnosis flag and returns through its normal path with no socket shutdown or close; the reader
then proceeds to the next record on the same stream. An unknown type therefore keeps the stream.
READ (app library, SDK 4.3.8). Inside a type 1 record, an inner opcode other than `100c` is
logged and dropped. READ.

| Type | Construction / handling (READ) |
|---|---|
| 1 | Master handshake. Out: RSA-encrypted inner query. In: master reply, AES-GCM with the stored master key/IV, AAD = 12-byte envelope. |
| 2 | Initial P2P request (out). Clear `IV[12]` + EC public-key slot[92] (104 bytes); rest AES-GCM. AAD = envelope + 104-byte prefix. |
| 3 | Initial P2P response (in). Whole body GCM with the cached ECDH key/IV; AAD = envelope. No clear prefix. |
| 4 | P2P handshake message. Clear LE32 server SID first; rest GCM; AAD = envelope + SID (16 bytes). |
| 5 | Keepalive, cleartext. Out body 12: LE32 server SID @0, u8 keepalive type @4, reserved @5..7, LE32 timestamp @8. In: exactly 28 bytes, same 12 then observed sockaddr16; expected type 2. |
| 14 | Server alert, GCM, AAD = envelope ([Alert (type 14)](#alert-type-14)). |
| 16, 17 | Compiled HMAC control sender: body 40, tag after first 20 body bytes. No receive branch. |
| 18, 19 | Compiled HMAC control sender: body 36, tag after first 16 body bytes. No receive branch. |
| 20, 21 | Compiled data sender: HMAC over envelope + first 16 body bytes, 20-byte tag appended. |
| 22, 23 | Compiled data sender: HMAC over envelope + all preceding body bytes, 20-byte tag appended. |

R3. Types 16..23 are compiled code only. The record2 support check returns 0, and requesting
integrity-only data mode 1 fails with -63. They MUST NOT be assumed negotiated. READ / INFERRED.
Their format (READ): HMAC-SHA1 keyed with a NUL-terminated string; types 16/17 body `{u8 command,
u8 reserved, LE16 session id, 16 bytes, tag20}` covering the first 32 packet bytes; 18/19 carry 12
bytes and cover 28; the data helper (≤ 1356 bytes) uses `{u8 0x10, u8 channel, LE16 id, RID8, u8
datatype, 3 reserved, data, tag20}`, even/odd type for relay/direct.

## Cryptographic primitives

R4. AES is **AES-128-GCM** with a 16-byte tag appended and included in the body length; no padding.
The writer rejects an all-zero key or IV. READ.

R5. Master material: random 16-byte AES key and 12-byte IV per attempt, sent inside the RSA-protected
type-1 query; the reply is decrypted with them. RSA uses the client's embedded 2048-bit master public
key in raw (no-padding) mode ([framing R12](framing.md#mask-from-the-licence)). READ.

R6. P2P-server material: the client has a P-256 (curve NID 415) key pair per attempt. For each
server it DER-decodes the first 91 bytes of the server's 92-byte EC key slot (from the master's
server list), computes ECDH **with no KDF**, takes the **first 16 raw shared-secret bytes** as the
AES key, and generates a random 12-byte IV. READ.

R7. Request nonces are nonzero 16-bit values from a random range; master and P2P nonces are kept
separately. The allocator tries to avoid tracked nonces but skips the last tracked value, so
collisions are possible. READ. A request nonce is not a GCM IV. Implementations SHOULD avoid active
collisions correctly and MUST still correlate source, context, UID and RID; a 16-bit nonce alone
cannot identify an attempt. INFERRED.

## Control layouts

Offsets are from the inner header H (after type 4's clear SID). Lengths are "inner / body" and
exclude the SID and tag. `sockaddr16` here: BE16 port @+2, IPv4 @+4, other bytes opaque unless the
sender zeroes them. The sender zeroes buffers first; a receive-only opaque field is not thereby
known to be zero from the server. READ.

### Master query `100b` (type 1, out)

88-byte plaintext (READ): H (magic `0204`, revision 29, length 72, opcode `100b`, route `18`); LE16
master nonce @16; zero[2] @18; AES key[16] @20; IV[12] @36; UID20 @48; realm[16] @68; u8 6 @84; u8
device-role flag @85; zero @86..87.

### Sent inner messages

| Opcode | Inner / body | Fields |
|---|---:|---|
| `0217` precheck (type 2) | 52 / 36 | LE16 P2P nonce @16; zero[2] @18; UID20 @20; LE32 connect/query argument @40; optional auth[8] @44 |
| `0127` registration (type 2) | see cloud-auth | Device registration body: [cloud-auth](../../auth/cloud-auth.md) |
| `0240` P2P request, route `34` | 288 / 272 | UID20 @16; four local sockaddr16 @36..99; RID8 @100; LE32 local NAT @108; zero @112..271; 8 copied auth bytes @272..279; zero @280..287. No nonce. |
| `0241` relay-info request | 60 / 44 | UID20 @16; RID8 @36; LE32 flag @44 (1 selected server; 0 unselected or already-connected); LE32 SDK @48 (app: `0x04030800`); LE32 protocol 29 @52; LE32 local NAT @56. Header: flags 0, sequence 0, route `24`, H+12/14/15 zero. No nonce, sockaddr, auth or port. |
| `030f` relay-info ACK | 44 / 28 | UID20 @16; RID8 @36; LE16 relay ID at H+12; route `24` client, `14` device |
| `020c` relay request | see cloud-auth | Timeout value 60, option 5 ([cloud-auth](../../auth/cloud-auth.md)) |
| `010e`, `012a`, `0806` | see cloud-auth | Relay knock response, sleep registration, connection report |

R8. The `0240` auth bytes come from the optional eight-byte IOTC auth setting, not the tunnel
password, and sit at H+272 (not the legacy H+280). Disabled local advertisement leaves the local
slots zero. READ.

### Received inner messages

| Opcode | Inner / body | Fields |
|---|---:|---|
| `100c` master result (type 1) | variable, ≥ 76 | LE16 master nonce @16; opaque[2] @18; UID20 @20; opaque[16] @40; observed sockaddr16 @56; opaque[2] @72; LE16 unit count @74; units @76 |
| `0218` precheck reply (type 3) | 72 / 56 exactly | LE16 nonce @16; opaque[2] @18; LE32 server SID @20; UID20 @24; LE32 seconds @44; opaque[12] @48; LE32 peer NAT @60; LE32 peer SDK @64; u8 auth-use @68; u8 capabilities @69 (bit 1: record2); opaque[2] @70 |
| `0128` registration reply (type 3) | 52 / 36 exactly | Nonce/SID/UID as `0218`; u8 server type @44; opaque[3] @45; LE32 timestamp @48 |
| `020d` relay result (type 4) | 48 / 32 | UID20 @16; signed LE32 result @36; RID8 @40. No nonce. |
| `030e` relay session info (type 4) | 104 / 88 | UID20 @16; LE32 relay allocation ID @36; client sockaddr16 @40; device sockaddr16 @56; RID8 @72; client/device SDK @80/84; client/device protocol @88/92; client/device NAT @96/100. No nonce. |
| `030d` punch instruction (type 4) | 312 / 296 | LE16 nonce @16; opaque[2] @18; UID20 @20; primary WAN sockaddr16 @40; four LAN sockaddr16 @56..119; RID8 @120; client/device NAT @128/132; eight more WAN sockaddr16 @136..263; opaque[32] @264; opaque[16] @296 |
| `010d` relay knock (type 4) | 52 / 36 | LE16 nonce @16; opaque[2] @18; UID20 @20; RID8 @40; LE16 requested port @48; opaque[2] @50 |
| `0129` notify-register, `012b` sleep ACK | 40 / 24 | LE16 nonce @16; opaque[2] @18; UID20 @20 (device context only) |

R9. `100c` units use the `{u8 type, u8 reserved, LE16 length}` header of
[framing R20](framing.md#receive-catalogue). Type 1: VID/PID/GID. Type 9: server list, an array of
**108-byte** entries (sockaddr16 @0, EC key slot[92] @16), count = length / 108. No IPv6 entry form
is established. READ.

The unit loop runs exactly the declared unit count from offset 76. Each unit must have its 4-byte
header and its declared extent inside the decrypted message; otherwise the whole `100c` is
rejected. Units of other types are skipped by their declared length. Bytes after the last
declared unit are not examined. In a type 9 unit, a remainder below 108 bytes is ignored. A later
unit of type 1 or type 9 replaces the values of an earlier one. READ (app library).

Only the server list count left after the loop matters. A `100c` whose final count is zero (no
type 9 unit, a type 9 unit shorter than 108 bytes, or a later empty type 9 unit after a non-empty
one) skips the list update and the query advance: the stored list is left unchanged, the UDP
query stays in state 1, the TCP query stays in state 4, and the device-side completion flag is
not set. The context is then released on the same exit as a successful update, with no error.
READ (app library). So a later empty unit does not erase a list installed by an earlier
`100c`; within one `100c` it cancels the earlier non-empty unit. A non-empty list merges into
the stored list for its VID/PID/GID group: an entry whose address is already stored updates its
key slot, a new address is appended, and stored addresses absent from the new list are kept.
READ (app library). The app library merge is purely additive: it has no "force update" flag and
never prunes (no such global exists in the app IOTC library, SDK 4.3.8, and the merge routine
contains no removal path). READ (app library, SDK 4.3.8). In the device library a one-shot "force
update" flag, when set, first removes stored entries that are absent from the new list and is then
cleared; this prune is device-only. In the device library the
flag is armed locally, not by any message: the SDK's daily server-list routine sets it on every
run after the first (IOTC initialization resets the first-run marker). Each run also restarts a
master re-query task (first run after 20 s, then every 86 400 000 ms), returns each P2P server to
the send-register state and starts device re-registration. The re-query task deletes itself while
the flag is clear. READ (device library). Only the caller that triggers the device daily routine
was not traced. unresolved. A client that merges
by address and never prunes stays consistent with every behaviour above. INFERRED.

R10. Protocol and NAT consumers of `030e` keep only the low byte. READ.

## Receive processing

R11. Type 4 order: known-server check (UDP) → cached key lookup → GCM verify/decrypt (SID in AAD) →
compare stored server SID → inner magic, length, opcode, identity and state checks. The outer record
SID selects the local attempt context; the server SID is the clear type-4 prefix. READ.

R12. Messages with nonces: `030d`, `010d`, `0129`, `012b` (and `100c`, `0218`, `0128`). `020d` and
`030e` correlate by RID/session and MUST NOT be parsed as nonce-bearing. READ / INFERRED.

| Message | Acceptance and action (READ) |
|---|---|
| `100c` | Expected master (UDP), outer context, master nonce, UID; parse units; only when the final server list count is non-zero: install the list, UDP query 1 → 2, TCP 4 → 5 |
| `0218` | Exact size, P2P nonce, UID, connecting context; install server SID and peer data; UDP precheck 5 → 6, TCP 11 → 12 |
| `030d` (new) | Exact size; nonce via outer context; reject recently refused RID ([connect: Attempt and cache lifetimes](connect.md#attempt-and-cache-lifetimes)); find session by **RID**; keep primary WAN, add up to eight WAN total (stop at zero IPv4, dedupe IPv4+port); keep four LAN slots; start WAN and first-LAN knocks; NAT sum 5 starts [try-port](connect.md#try-port-traversal). Not by itself success. |
| `030d` (repeat) | Connected (status 2) with P2P state 3 and saved WAN port: re-knock the kept WAN endpoint. Creating (status 1) with P2P state 3: re-knock the kept endpoint. No reset, no new success. |
| `020d` | Exact size; RID/context/state match; result 0 advances relay allocation, -7 stays pending. Not a usable path by itself. |
| `030e` | Exact size; reject stale RID; client uses **device** fields, device uses **client** fields; install relay path 2 (UDP) or 3 (TCP) and relay ID; send `030f`; UDP relay 4 → 5, TCP 18 → 20. Connected sessions may re-ACK. |
| `010d` | Device/global context; exact size; nonce, UID, RID; requested-port and capacity checks; reply `010e`. |
| `0129` / `012b` | Device context; exact size; UID and nonce; schedule registration / feed sleep list. |

R13. In the inspected app path, the `030d` lookup by RID does not check that the found session
matches the outer record SID. READ. Implementations MUST require that agreement, MUST check every fixed length, unit header,
unit extent and array stride before access, and MUST reject disposed or cancelled attempts while
still allowing the repeat-punch re-knock on a live association. INFERRED. This is not evidence of a
GCM bypass.

### Alert (type 14)

R14. Decrypted alert: LE32 server SID @0, LE16 nonce @4, u8 alert @6, u8 triggering record type
@7, u8 protocol revision @8. Alert 1 = device not logged in (as `0227`); alert 2 = asleep (as
`0229`); others logged. If the stored server SID is zero, the app installs the alert's SID
**before** checking the nonce; otherwise the SID must match. READ.

The alert byte is examined only after the nonce check. Values other than 1 and 2 are logged and
the handler returns an error without a status update, so the only state change an unknown value
can follow is the SID install above. READ (app library). Implementations SHOULD make no state
change for an unknown alert value. INFERRED.

R15. The app has no nine-byte minimum check, so a short authenticated alert reads zeros for missing
fields; the triggering type is only logged. READ. Implementations MUST require at least nine
plaintext bytes and validate identity and state before acting. INFERRED.

## GCM key, IV and cache contract

R16. **Vendor design, not a recommendation:** a cached AES-GCM key/IV pair is reused for distinct
rendezvous records with the same server, including the opposite-direction receive path. Neither
encoder nor decoder advances the IV; RID and request nonce do not alter it. Implementations that
need compatibility MUST NOT add IV counters or direction-specific keys; removing the reuse needs a
negotiated protocol change. READ / INFERRED. No attack or server nonce behaviour was tested.

| Scope / event | State and wire use (READ) |
|---|---|
| New attempt | Allocate RID, master and P2P nonces, master AES material, local EC key pair. State belongs to the attempt, not a TCP connection. |
| Server list install/update | Merge by address within the VID/PID/GID group; entries are not removed except by the one-shot force-update prune (R9). Each server entry gets a local wall-clock marker when installed or when any of its 92 key-slot bytes changes; unchanged entries keep their marker. No timestamp is on the wire. |
| Cache lookup | Up to 12 entries per session/device context, keyed by server **address string** (not port or direction). Needs server key metadata with a nonzero marker. |
| New entry or changed marker seconds | Derive key and IV as R6; copy the server entry's marker into the cache. |
| Matching entry | Compare only the **seconds** of the markers; equal seconds return the existing pair. A key change within the same second can leave the old pair in use. No per-packet refresh. |
| Type 2 send | Publish cached IV and local key slot in the clear prefix; encrypt with the cached pair. |
| Type 3 receive | Same pair; no IV in the reply. Accepted reply installs the server SID. |
| Type 4 send/receive | Same pair; AAD = envelope + server SID. |
| Type 14 receive | Same pair; AAD = envelope. |
| Disposal / failure | Release attempt state and EC key. A new attempt does not carry over an old record SID, and takes the next RID from the counter ([session: Identity](session.md#identity)); it is not checked against earlier RIDs. Lookup fails without context, metadata or a free slot; no eviction or rotation. |

R17. Changing only the 92nd key-slot byte counts as a change, although DER decoding uses 91 bytes.
READ. External server key rotation policy is unresolved (server-side).

R18. DTLS record nonces are unrelated to this reuse ([dtls: Record protection](dtls.md#record-protection)). READ.
