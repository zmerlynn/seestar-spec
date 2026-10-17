# Cloud auth: record-based master authorization and precheck

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file covers the
encrypted record layer that the Android SDK 4.3.8 uses for the master query, P2P-server key
agreement, device registration and precheck. The legacy unencrypted forms are in
[master-legacy.md](master-legacy.md); relay messages carried in the same records are in
[relay.md](relay.md). The full GCM key/IV lifetime contract and peer records belong to
[Kalay/IOTC session](../../transport/iotc/index.md).

Basis: static analysis of app 3.3.2 (client SDK 4.3.8); crypto helpers cross-checked against
firmware 9.31. Reply layouts are from the client's record handler.

## Outer record

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 0 | 4 | LE32 | Magic `0x0000cc51` (wire `51 cc 00 00`) |
| 4 | 1 | u8 | Version; 2 from these senders |
| 5 | 1 | u8 | Record type |
| 6 | 2 | LE16 | Payload length, excluding these 12 bytes |
| 8 | 4 | LE32 | Record SID; `0xffff` = the SDK's device record, other values = client connection records |
| 12 | … | | Type-dependent payload |

R80. A receiver requires at least 12 bytes, at most 1416 (`0x588`), the magic, and a length that
matches the frame; over TCP it may collect more bytes first. READ.

Record types handled by the server-control handler (READ):

| Type | Direction | Protection |
|---:|---|---|
| 1 | master request (send) / master reply (receive) | Request: raw RSA-2048. Reply: AES-128-GCM, tag 16, AAD = outer 12 bytes |
| 2 | P2P initial handshake (send only; rejected on receive) | Clear prefix IV[12] + public-key slot[92]; rest GCM; AAD = outer 12 + clear prefix (116 bytes) |
| 3 | P2P initial-handshake reply (receive) | Whole payload GCM; AAD = outer 12 bytes |
| 4 | server control (send and receive) | Clear LE32 P2P-server session ID, then GCM; AAD = first 16 wire bytes |
| 5 | keepalive (send and receive) | None. See below |
| 14 | server alert (receive) | Whole payload GCM; AAD = outer 12 bytes. See [relay.md: Server alerts](relay.md#server-alerts) |

Other types go to unsupported handling. READ.

**Type 5 keepalive** (READ): request payload 12 bytes, reply payload exactly 28 bytes. Payload +0
LE32 server session ID; +4 kind byte (request 1; a reply kind other than 2 is logged as
unexpected); +8 LE32 timestamp; other request bytes zero; reply +12 is a 16-byte observed
address.

### Inner header

Plaintext inside records starts with the same 16-byte header as legacy messages
([master-legacy.md: Legacy packet header](master-legacy.md#legacy-packet-header)): magic `0x0204`, version
`0x1d`, flags 0, LE16 body length at 4, zero 6–7, opcode at 8, control at 10, zero 12–15 unless
stated. READ. Offsets in this file are relative to that inner header unless marked "outer".

## Crypto primitives

- **RSA:** raw public operation, no padding (OpenSSL padding value 3). The plaintext is
  right-padded with zeros to the modulus size. READ.
- **AES-GCM:** selector 1 = AES-128-GCM, 16-byte key, 12-byte IV, 16-byte tag appended, no
  padding (matches AEAD_AES_128_GCM of RFC 5116). Record wrappers accept only this selector.
  READ.
- **Decrypt guard:** rejects null input, payloads over 1404 bytes (`0x57c`), an all-zero key or an
  all-zero IV; a failed tag returns -8013. READ.
- **ECDH:** curve number 415 (named `prime256v1`, i.e. P-256, in OpenSSL's public header); the
  shared secret is computed with no KDF. READ.
- **Random material:** the master AES key is four `rand()` words (16 bytes), the IV three words
  (12 bytes); nonces are nonzero 16-bit values from a range helper. The allocator tries to
  exclude collected nonces, but an indexing mismatch skips the most recently collected one, so
  collision-free allocation is not established. READ. Replies MUST be correlated by the full
  server, session and UID context, not by nonce alone (INFERRED). The master nonce and the P2P nonce are separate. Uniform or collision-free nonces MUST
  NOT be assumed. INFERRED.

R81. Keys and IVs are not advanced per message. A cached server key/IV pair is reused while the
cache's update-time seconds match; this reuse of a GCM key/IV pair is the vendor's design. READ.
A compatible implementation MUST accept it from peers; a new implementation SHOULD NOT copy it
for its own outbound traffic where interoperability allows. INFERRED. Lifetime rules:
[Kalay/IOTC session](../../transport/iotc/rendezvous-gcm.md#gcm-key-iv-and-cache-contract).

## Master query (record type 1)

The client encrypts its query with the **master public key**, a 2048-bit RSA key embedded in the
client SDK, reproduced in [embedded-constants.md: Master-query public key](embedded-constants.md#master-query-public-key).
Only opcode `0x100b` is sent this way. READ.

**`0x100b` query plaintext**, 88 bytes, zero-initialized (READ):

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 16 | Header: magic, `0x1d`, flags 0, LE32 `0x48` at 4 (body 72), opcode `0x100b`, control `0x18` |
| 16 | 2 | LE16 master nonce |
| 18 | 2 | Zero |
| 20 | 16 | AES key the master must use for its reply |
| 36 | 12 | IV the master must use for its reply |
| 48 | 20 | Target UID |
| 68 | 16 | Realm, fixed width |
| 84 | 1 | Constant 6 |
| 85 | 1 | 1 if record SID is `0xffff`, else 0 |
| 86 | 2 | Zero |

The 88 bytes are zero-padded to 256, raw-RSA encrypted, and sent as a 268-byte type-1 record.
READ.

**`0x100c` reply**, type 1, decrypted with that request's key and IV. Checks: magic `0x0204`,
body ≤ 1388 (`0x56c`), master nonce at 16, UID at 20, active record state; over UDP the source
must be a known master. A failing reply is ignored and records a master failure. READ.

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 16 | Header |
| 16 | 2 | Master nonce |
| 18 | 2 | unresolved (server-side) |
| 20 | 20 | UID |
| 40 | 16 | unresolved (server-side) |
| 56 | 16 | Observed address, to NAT tracking |
| 72 | 2 | unresolved (server-side) |
| 74 | 2 | LE16 TDU count |
| 76 | … | TDUs |

TDUs as in the legacy reply. Type 1: VID/PID/GID (three LE16). **Type 9**: P2P server list with
108-byte entries (16-byte address entry + 92-byte public-key slot); count = length / 108. Unknown
types are skipped after bounds checks. The list is stored per VID/PID/GID and region with the
server keys (32 group slots). A matching reply moves UDP query 1 → 2 or TCP 4 → 5. READ.

R82. The legacy `0x1008` (type 2, 16-byte entries, no keys) and `0x100c` (type 9, 108-byte
entries) are not byte compatible. READ.

## Server key agreement

The client creates a P-256 key pair; its DER public key (91 bytes) is copied into a zeroed
92-byte slot. For each P2P server, the server's first 91 key-slot bytes are decoded, the ECDH
secret is computed, and its **first 16 bytes are used directly as the AES-128 key**; a fresh 12-byte
IV is generated. There is no hash or HKDF step. READ.

R83. An implementation MUST derive the per-server key exactly so: `key = ECDH(P-256)[0..15]`.
READ (behaviour).

## Initial handshake (record type 2)

Outer payload: IV[12], client public-key slot[92], then the GCM-encrypted inner message and tag.
The first 104 payload bytes are clear and authenticated (AAD 116 bytes). Two inner messages are
sent this way. READ.

| Opcode | Role | Inner / body | Layout after header | Control |
|---|---|---:|---|---|
| `0x0217` precheck record | client | 52 / 36 | 16 LE16 nonce; 18 zero[2]; 20 UID[20]; 40 caller's LE32; 44 auth key[8] or zero | `0x24` |
| `0x0127` device register record | device role | 146 / 130 | 16 LE16 nonce; 18 zero[2]; 20 realm[16]; 36 UID[20]; 56 LE32 TDU count 2; TDUs from 60 | `0x14` |

`0x0127` TDUs (READ): TDU 1 header at 60 (type 1, length 40); 64–79 local address (16); 80 LE32
SDK version `0x04030800`; 84 LE32 NAT type; 88 auth[8]; 96 LE32 timestamp (seconds); 100–103 zero.
TDU 2 header at 104 (type 2, length 38); 108 version string (37 characters) plus NUL.

## Handshake replies (record type 3)

Both replies need a matching nonce and UID. READ.

**`0x0218` precheck reply** (client records), exactly 72 inner bytes (body 56):

| Offset | Size | Meaning |
|---:|---:|---|
| 16 | 2 | Nonce |
| 18 | 2 | unresolved (server-side; no field read) |
| 20 | 4 | LE32 P2P-server session ID |
| 24 | 20 | UID |
| 44 | 4 | LE32 `beforeSec` (seconds; stored as ms) |
| 48 | 12 | unresolved (server-side) |
| 60 | 4 | LE32 NAT type |
| 64 | 4 | LE32 API version |
| 68 | 1 | Auth-use byte |
| 69 | 1 | Capability flags; bit 1 = supports record type 2 |
| 70 | 2 | unresolved (server-side) |

It stores the server session ID and auth/capability data and moves UDP 5 → 6 or TCP 11 → 12. READ.

**`0x0128` register reply** (device record `0xffff`), exactly 52 bytes (body 36): nonce at 16,
server session ID at 20, UID at 24, server-type byte at 44, opaque[3] at 45, LE32 timestamp at
48. READ.

R84. The server session ID from a type-3 reply is the clear SID that prefixes every later type-4
record to that server. READ.

R85. Receivers MUST check length, nonce and UID before acting on a reply. The inspected handler
checks these for types 1 and 3; it does not establish rejection of every malformed packet. READ
(checks) / INFERRED (obligation).
