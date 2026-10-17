# IOTC DTLS session protection

Part of [Kalay/IOTC session](index.md). This file specifies how DTLS protects peer data: its
encapsulation in IOTC data packets, the PSK identity and key, the conditional default version and
cipher suite, the key schedule, record protection and retransmission timers. Below: IOTC data
packets on channel 0 ([framing: Data, alive and close packets](framing.md#data-alive-and-close-packets)). Above: RDT packets
([rdt.md](../rdt.md)), which carry the [P2P tunnel](../p2p-tunnel.md). Credentials come from
[cloud-auth](../../auth/cloud-auth.md). Labels: [index: Conventions](index.md#conventions).

Basis: static analysis of the app libraries (app 3.3.2) and the device library (firmware 9.31),
both linking OpenSSL 3.1.4. No handshake was observed.

## Encapsulation and role

R1. Each DTLS record is the payload of an IOTC data packet with **datatype 1** on **IOTC channel
0**. With an extended RID the record starts at packet offset 28. DTLS is never sent as bare UDP.
READ.

R2. The RDT layer creates a DTLS context, installs PSK client/server callbacks, attaches the SSL
object to a BIO bound to (SID, channel), sets the timeout and runs connect (app, client) or accept
(device, server). Quiet shutdown is set and partial IOTC scrambling enabled. READ.

R3. The device creates secure RDT on channel 0 with a 30000 ms timeout when authentication
callbacks are installed. The app's tunnel connect obtains a SID, connects in parallel mode and
creates secure RDT on channel 0 with 30000 ms. RDT creation failure closes the IOTC session;
later tunnel login failure destroys RDT and closes IOTC. READ.

R4. A record boundary is preserved by the IOTC packet. An implementation MUST feed one IOTC data
payload to the DTLS stack as one datagram. INFERRED.

## Version and cipher suite

R5. Condition (prominent): the profile in this section holds **only if** no runtime OpenSSL
`system_default` or provider configuration changes the compiled policy, the PSK callbacks are used
without added certificates or DH parameters, and the peers share an EC group. READ / INFERRED.
Live configuration is unresolved: the libraries honour `OPENSSL_CONF` or a build-time
`ssl/openssl.cnf` path, which the shipped archive does not contain.

R6. Both libraries run at security level 1, which rejects DTLS 1.0. The method table has DTLS 1.2
(`fe fd`), DTLS 1.0 (`fe ff`) and an old compatibility value, and no DTLS 1.3. The usable version
is therefore **DTLS 1.2**. The first record's legacy version field need not be `fe fd`. READ.

R7. No inspected path sets a cipher list. Both default expressions are
`ALL:!COMPLEMENTOFDEFAULT:!eNULL`; the 167-entry cipher tables are identical in app and device. With
no certificate, RSA-PSK is excluded; with no DH setup, DHE-PSK is excluded. Server preference is off,
so the server follows client order. READ.

R8. Predicted common PSK set, in client order (INFERRED, calculated, not captured):

| Wire ID | OpenSSL name |
|---|---|
| `cc ac` | ECDHE-PSK-CHACHA20-POLY1305 |
| `00 a9` | PSK-AES256-GCM-SHA384 |
| `cc ab` | PSK-CHACHA20-POLY1305 |
| `00 a8` | PSK-AES128-GCM-SHA256 |
| `c0 38` | ECDHE-PSK-AES256-CBC-SHA384 |
| `c0 36` | ECDHE-PSK-AES256-CBC-SHA |
| `00 af` | PSK-AES256-CBC-SHA384 |
| `00 8d` | PSK-AES256-CBC-SHA |
| `c0 37` | ECDHE-PSK-AES128-CBC-SHA256 |
| `c0 35` | ECDHE-PSK-AES128-CBC-SHA |
| `00 ae` | PSK-AES128-CBC-SHA256 |
| `00 8c` | PSK-AES128-CBC-SHA |

The full default client offer is 53 suites (26 PSK) plus the renegotiation SCSV `00 ff`. INFERRED.

R9. Predicted selection: **`TLS_ECDHE_PSK_WITH_CHACHA20_POLY1305_SHA256` (`cc ac`)**. INFERRED.
Three sessions between the official Android app and a live device (2026-10-10, 2026-10-11,
2026-10-13) negotiated DTLS 1.2 (`fe fd`) with `cc ac`. OBSERVED (client-side records; versions not
recorded). A client session on 2026-10-16 negotiated the same. OBSERVED 2026-10-16.
A client offering only `00 a8` would share a cipher under the same policy but would not reproduce
the app's offer or the predicted choice; untested. INFERRED. Default groups start 29, 23, 30, 25,
24; the DTLS group is negotiated separately from the rendezvous P-256 key. INFERRED.

R10. Implementations SHOULD use a standard DTLS 1.2 library with these callbacks rather than a
custom handshake. INFERRED.

## Identity and PSK

R11. PSK identity: the cloud-supplied **username** bytes up to NUL, with no prefix (no
`AUTHPWD_`/`AUTHTKN_`). PSK: the **32 raw bytes of SHA-256(password bytes up to NUL)** (not hex, not
the eight-byte IOTC auth field, not the licence). READ.

R12. An empty username or password fails client authentication; an empty returned password fails
server authentication. The server looks up the password by identity
([session R2](session.md#library-setup-on-each-side)). READ.

R13. Buffer capacities: identity 256 bytes; app password buffer 1024 bytes; device password buffer
**32 bytes** (plus a terminator). Clients MUST keep the password within the device limit. The
device's copy is unbounded (`strcpy`) and MUST NOT be used as a model. READ / INFERRED.

R14. The ServerKeyExchange carries a BE16-length identity hint (empty here), EC parameters and a
public key; the ClientKeyExchange carries a BE16-length identity (no NUL) and EC public data. The
ECDHE secret is a fresh exchange inside DTLS; the rendezvous ECDH secret MUST NOT be substituted.
READ / INFERRED.

## Key schedule

R15. ECDHE-PSK premaster: `BE16(len(Z)) || Z || BE16(32) || PSK`; plain PSK uses a 32-byte zero
other-secret. Master secret: 48 bytes from the TLS PRF with label `master secret` and the randoms,
or `extended master secret` and the handshake hash when EMS is negotiated. Key expansion uses
server-random then client-random. READ. DOC: RFC 5489, RFC 7627.

R16. For `cc ac` the SHA-256 PRF yields 88 key-block bytes: client write key (32), server write key
(32), client write IV (12), server write IV (12). No MAC keys. READ.

## Record protection

R17. For `cc ac` (READ; DOC: RFC 7905):

- Nonce = directional write IV XOR `(zero[4] || BE16(epoch) || BE48(sequence))`.
- AAD = the standard 13 bytes: epoch and sequence, content type, version, **plaintext** length.
- A 16-byte tag is appended; no explicit nonce and no padding. The record length includes the tag.

R18. The DTLS 1.2 record header (13 bytes) carries type, version `fe fd`, epoch, 48-bit sequence and
length. DOC (RFC 6347 §4.1). Useful to recognize records in decoded IOTC data; not proof of the
negotiated version.

## Timers and shutdown

R19. App: a timer callback returns **500000 µs** initially and doubles the previous value, with no
cap. The connect loop retries on want-read/want-write and fails with -50006 when the configured
millisecond timeout passes (clamped to `0x7fffffff`). READ.

R20. Device: no callback; the library default starts at **1 s**, doubles to a **60 s** cap and fails
when the timeout count reaches **13**. READ. The 30000 ms tunnel handshake deadline usually ends
attempts first. INFERRED.

R21. RDT's own 500000 µs retransmission timer is separate ([rdt.md](../rdt.md)). READ.

R22. Both sides use quiet shutdown: teardown MUST NOT expect a close-notify exchange. READ /
INFERRED.

## Notes

R23. DOC: the vendor describes the extended tunnel APIs as the DTLS path and an optional
unencrypted LAN-direct mode enabled by initialize argument 1 on both ends, which matches Seestar's
arguments. Whether a given connection uses it is unresolved; see Q29 in
[00-overview.md: Open-question register](../../00-overview.md#open-question-register) and
[p2p-tunnel/session.md: LAN-direct bypass](../p2p-tunnel/session.md#lan-direct-bypass).

R24. Published research on other ThroughTek products (other SDK versions) MUST NOT be used for
identifiers, ports or PSK identity rules here. INFERRED.
