# Kalay/IOTC session

This chapter covers the ThroughTek Kalay "IOTC" layer: rendezvous with master and P2P servers,
NAT traversal, direct/relayed session selection, the session packet format that carries peer
data, and the DTLS profile that protects it. Below it sit plain UDP and TCP sockets (and, on the
LAN, [discovery](../lan-discovery.md)). Above it sit the [RDT reliable channel](../rdt.md) and the
[P2P tunnel](../p2p-tunnel.md). The account-side inputs (licence, UID, credentials) come from
[cloud authorization](../../auth/cloud-auth.md). Stack overview: [00-overview](../../00-overview.md).

Sub-chapters:

| File | Contents |
|---|---|
| [framing.md](framing.md) | Legacy 16-byte header, scrambling, licence mask derivation, legacy message catalogue and byte layouts, data/alive/close packets |
| [connect.md](connect.md) | Endpoint discovery, NAT classification, UDP/TCP path selection, LAN establishment, try-port traversal, attempt lifetimes |
| [session.md](session.md) | Session identity, data path, liveness, path migration, channels, timers, close, device-side optional traffic |
| [rendezvous-gcm.md](rendezvous-gcm.md) | Newer encrypted rendezvous records (`51 cc 00 00` envelope), control layouts, GCM key/IV cache contract |
| [dtls.md](dtls.md) | DTLS inside IOTC data, PSK identity, conditional default profile, key schedule, timers |

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
implementers of a client or a stand-in device. Sentences that say what "the app library" or
"the device library" does are descriptions.

Labels (see `CONVENTIONS.md`):

- **READ**: seen by static analysis of the shipped binaries.
- **OBSERVED**: seen on a real device or in live traffic; date given. This chapter has none.
- **INFERRED**: synthesis, interpretation or proposed implementation policy.
- **unresolved**: not established either way.
- **DOC**: taken from public ThroughTek documentation or an RFC. It describes the vendor's
  public statements, not this binary.

Two code bases are referred to throughout:

- **App library**: the IOTC "T" libraries selected by Android app 3.3.2 (SDK version word `0x04030800`). This is the
  modern client.
- **Device library**: the IOTC code linked into the imager daemon of firmware 9.31 (SDK version word `0x04030603`,
  64-bit build). It acts as the server (tunnel listener). The 32-bit firmware build carries the
  same SDK version but did not get a full control-flow audit. Firmware 9.75 keeps the version word ([Firmware 9.75 build comparison](#firmware-975-build-comparison)).

Notation (INFERRED, explanatory names, not vendor declarations): `H` is the decoded 16-byte legacy
header and `B` its body (`B+0` is packet offset 16). `LE16`/`LE32` are unsigned little-endian
fields; `BE16` big-endian. `UID20` is exactly 20 bytes (no added terminator). `RID8` is two LE32
words forming the attempt cookie. `sockaddr16` is the 16-byte IPv4 wire address of
[framing: Common field types](framing.md#common-field-types). Fields marked reserved or opaque MUST NOT be given
new meaning.

Basis: static analysis of app 3.3.2 and firmware 9.31, plus a build comparison with firmware 9.75
([Firmware 9.75 build comparison](#firmware-975-build-comparison)). No target code was run and no device or server was contacted. No statement here
claims a successful live connection. Statements are firmware 9.31 unless tagged.

### Firmware 9.75 build comparison

Firmware 9.75 (app 3.4.0) keeps the device SDK at version word `0x04030603` with the same revision
strings (48 characters in the 64-bit build, 43 in the 32-bit build), so it is the same SDK code
(READ, both builds). What changed is the build, not a protocol generation:

- The SDK is built without its logging, so the source-path and log strings are gone, and many static
  handlers are inlined or folded. In the 64-bit imager the named out-of-line message handlers fall from
  24 to 15. The count change is compiler inlining and folding, not a protocol change (READ for the opcode
  set; the inlining of individual handlers is INFERRED from their callees appearing in the dispatcher).
  The packet dispatcher dispatches the same opcode set as in 9.31: the 0x4xx table of 40 entries matches the
  9.31 mask chain, and 0x501/0x503, 0x511/0x513, 0x521/0x523 and 0x601 to 0x604 are unchanged. The
  pair 0x103 and 0x10b is folded into one compare (both reach the relay knock handler), and 0x215/0x216
  still reach the precheck-reply handler. No master or relay wire message was added or removed. READ.
  - Fifteen handlers remain out of line: LAN search, precheck reply, relay packet (server to device),
    P2P packet (client to device), P2P punch (type 2), relay knock, relay session info (both forms), P2P
    packet (device to client), P2P knock reply and its type 2 form, relay request reply (type 2) and the
    three small close and alive handlers (`RLY_CLOSE_S2C`, `RLY_ALIVE_S2C`, `P2P_CLOSE_C2D`). The last three
    are newly out of line, with their bodies inline in 9.31 (INFERRED).
  - The relay-packet pair (server to client and server to device, identical callee sets in 9.31) is
    folded into one handler (READ). `RLY_KNOCK1` and `RLY_KNOCK2` are merged into one `RLY_KNOCK`; which opcode selects
    which variant was not decoded (INFERRED merge).
  - `HELLO_R`, `NOTIFY_DEVICE_REGISTER`, `REGISTER_SLEEP_R`, `CHECK_DEVICE_STATUS_R`, the P2P alive pair
    and the knock and punch type 1 family are inlined into the dispatcher (READ: their callees are
    direct callees of it).
  The 32-bit build has a different emitted/inlined split again (for example the query-device reply and
  the relay alive and P2P close handlers), so handler names MUST NOT be used as a cross-build catalogue
  of supported messages; no parity comparison of the 32-bit logic was made.
- Several utility symbols are gone (error-code translation, tunnel close/pause helpers, a
  per-session limit helper) and the creating-session recycler is no longer a named function. Its 10000 ms
  and 60000 ms constants are not new: in 9.31 they sit in the recycler, and in 9.75 the same immediates
  appear inline in the LAN search, the P2P punch (type 2) and the relay knock handlers next to the task
  creation and session-task insertion calls (READ for the immediates, INFERRED for "inlined recycler";
  [connect.md: Attempt and cache lifetimes](connect.md#attempt-and-cache-lifetimes)). They are not new timers.
- The `0x50` constant in the server-version update call is the 80-byte stride of the server record
  table with a protocol-version byte stored at offset 22 of the record; it is not a wire constant (READ).
- Where the packet handler was compared by call sequence and immediates (master, relay, knock,
  punch handlers), it is unchanged. The session limits (64 sessions, 74
  pre-sessions and the 0x1760 session stride) are unchanged where the allocators were compared.
  Reply builders, and the logic (as opposed to symbols) of the 32-bit build, were not diffed.

## Connection sequence

READ. Starting from an authorized account, the ZWO cloud "online-link" request returns a Kalay
licence string, the device UID, a tunnel username and password, and a cloud connection id. Their
roles:

| Input | Role |
|---|---|
| Licence | Authorizes the SDK, selects master-server names, and yields the 16-byte legacy scrambling mask ([framing: Scrambling](framing.md#scrambling)). |
| UID | Names the rendezvous target device. |
| Username / password | Later DTLS PSK identity and key ([dtls.md](dtls.md#identity-and-psk)). |
| Cloud connection id | Cloud allocation, report and stop only; never a packet field. |

The app library does not derive the separate optional eight-byte IOTC auth field from the tunnel
password in the inspected path. READ. Details: [cloud-auth](../../auth/cloud-auth.md).

```text
Account/cloud HTTPS                   separate from Kalay transport
  online-link -> licence, UID, credentials, cloud connection id

Master / P2P-server control           over UDP or a framed TCP stream
  modern 12-byte record envelope
    type 1 out: RSA(inner IOTC control H16 + body)
    type 1 in:  GCM(master reply)
    type 2:     clear IV12 + EC key slot92 + GCM(initial IOTC control)
    type 4:     clear server SID4 + GCM(inner IOTC control H16 + body)
  (device library: legacy scrambled frames instead)

Authenticated peer / relay data       over the selected IOTC UDP or TCP path
  scrambled legacy IOTC H16 [+ LE32(12) + RID8 extension]
    datatype 1: DTLS record (header13 + protected RDT packet + tag)
      decrypted RDT header20 + payload            -> rdt.md
        reliable ordered byte stream
          P2P tunnel header4 + payload            -> p2p-tunnel.md
            forwarded application TCP bytes
```

## Layers and identifiers

R1. Peer data uses opcodes `0407` (client to device) and `0408` (device to client) on a direct
path; `0504` (client) and `0502` (device) when sending to a relay; `0503` and `0501` when
received from a relay. READ.

R2. Extended (RID) data starts with `LE32(12) || RID8` after H, so a DTLS record begins at packet
offset 28. The IOTC channel is at H+14; the datatype is the low two bits of H+15. The Seestar
authenticated tunnel uses **IOTC channel 0, datatype 1**. READ.

R3. Partial scrambling covers the first **64 bytes of the IOTC packet** (header included), not 64
bytes of RDT or DTLS plaintext. READ.

R4. Peer data is not wrapped in a modern record envelope, does not use the rendezvous GCM key or
IV, and carries no extra tunnel length prefix. READ.

| Identifier | Scope (READ) |
|---|---|
| Cloud connection id | Allocation/report/stop; not a packet channel id |
| Process-local IOTC SID / outer record SID | Local session index chosen by the SDK; the outer modern record carries its context, with the special device context `0x0000ffff` |
| P2P-server SID | Server-assigned LE32; clear prefix of type-4 records, covered by GCM AAD |
| Request nonce (16-bit) | Master/P2P request correlation; not a GCM IV; the allocator is not collision-free |
| RID8 | Attempt identity/cookie; a short compatibility format also exists |
| Relay allocation ID | Low 16 bits carried at H+12 on relay paths |
| IOTC channel | 0 to 31; the Seestar tunnel uses 0 |
| RDT specific-ID byte | Local allocator 1 to 254; peer association within SID/channel ([rdt.md](../rdt.md)) |
| Tunnel channel byte | One forwarded TCP connection; independent of all the above ([p2p-tunnel.md](../p2p-tunnel.md)) |

R5. Stream boundaries: RDT sequence numbers count packets, but its read/write API carries an
ordered byte stream. Tunnel frames can span RDT packets and reads, and several frames can share
one read. TCP segment boundaries at a local proxy are not tunnel frame boundaries. READ.
Receivers MUST reassemble tunnel frames from the byte stream. INFERRED.

## Security summary

R6. The legacy scrambling is a keyed, reversible byte transform with no IV, chaining or tag. It is
obfuscation, not authenticated encryption. INFERRED (from the complete READ transform).

R7. Rendezvous records use AES-128-GCM with a key/IV pair that the vendor **reuses** across
distinct records and both directions. This is the vendor's design, not a recommendation.
Implementations MUST NOT invent IV counters or key separation if they want compatibility.
READ / INFERRED. See [rendezvous-gcm: GCM key, IV and cache contract](rendezvous-gcm.md#gcm-key-iv-and-cache-contract).

R8. Under unmodified compiled OpenSSL policy, the predicted peer protection is DTLS 1.2 with
`TLS_ECDHE_PSK_WITH_CHACHA20_POLY1305_SHA256` (`cc ac`). This is a conditional static prediction.
READ / INFERRED. Live sessions negotiated exactly this (DTLS 1.2, `cc ac`); OBSERVED 2026-10-10
to 2026-10-16 ([dtls.md R9](dtls.md#version-and-cipher-suite)). DTLS record nonces are independent of the rendezvous GCM reuse.
See [dtls.md](dtls.md).

## Open questions

- Firmware 9.75: the opcode-to-variant mapping of the merged relay knock handler, the LAN-search
  reply builder and the 32-bit build's logic ([Firmware 9.75 build comparison](#firmware-975-build-comparison)). unresolved.

- Legacy punch/relay variant tails, unknown modern metadata/tail fields and ignored sockaddr
  bytes. Local consumers can be traced further; server meaning needs server evidence or decoded
  traffic. unresolved. (The `0232` status reply's two words now have a local-consumer role; see
  [cloud-auth/master-legacy.md](../../auth/cloud-auth/master-legacy.md#other-legacy-authorization-messages).
  Its second word's absolute unit remains unresolved.)
- External server key rotation triggers; the live OpenSSL configuration and providers; the negotiated
  extensions and group (version and cipher are observed, R8); modern TCP record coalescing; scheduler timing.
  Need observation. unresolved.
- App cancellation interleavings, optional LAN-direct selection, remaining option defaults,
  exhaustive alternate-entry dispatch. unresolved. (The device's tunnel credentials arrive from
  the cloud and it sets no eight-byte auth key: [sdk-licence.md R46](../../auth/cloud-auth/sdk-licence.md#device-side-sdk-start).)
- The app loads only the "T" libraries (IOTC, RDT, P2PTunnel and Global). READ (app). The
  non-"T" IOTC library exports the same symbol names. The "T" build differs in its imports only
  by four logging and error-string imports, and it carries far more strings (log text). READ (app
  library, SDK 4.3.8). Full equivalence of the 32-bit firmware build, code-level equivalence of
  the non-"T" library including its optional HMAC record modes, and historical compatibility
  remain unresolved.
- No capture has validated the packet layouts, loss/reorder behaviour, attempt reuse or the
  try-port algorithm. unresolved.
- Server-side meaning of the `0241` flag and the conditions under which a server answers with
  `030e`. unresolved.
- A bitfield grammar for the legacy routing word. Only the builder values of
  [framing R1](framing.md#legacy-header) and the refusal high byte `0x02` are established.
  unresolved.
- A hello-serial lifetime. The app library does not compare the reply serial
  ([framing R24](framing.md#receive-catalogue)); any serial-matching window is local policy.
  unresolved.
- A wire generation discriminator for attempts. Legacy frames carry no generation field; the only
  stale-RID rule found is the recent-RID list, which rejects only RIDs refused in a LAN-search
  precheck, not closed ones ([connect: Attempt and cache lifetimes](connect.md#attempt-and-cache-lifetimes)).
  Telling an old attempt's frame from a new one with the same visible UID, RID and serial is
  local policy. unresolved.
- Server meaning of modern record types other than 1 to 5 and 14, of `100c` unit types other
  than 1 and 9, and of alert codes other than 1 and 2. unresolved.
- Whether a master ever sends a `100c` with an empty server list (the app library's handling of
  an empty list is READ). unresolved. The trigger of the device daily routine that arms the
  force-update prune: see [rendezvous-gcm R9](rendezvous-gcm.md#received-inner-messages).

## Appendix: How to validate on a live device (non-normative)

All steps INFERRED proposals; none has been run.

1. Passive capture, with the owner's consent, at an owner-controlled router: idle registration,
   one connection, traffic and a normal disconnect. Record app and firmware versions and
   monotonic times.
2. Decode: keep original datagrams. Derive the scrambling mask locally from the authorized
   licence, never publishing licence or account material. Check magic, lengths, flags, exact
   re-encoding and sockaddr byte order, including 16/64-byte boundaries and odd residual lengths.
3. Transport: separate legacy frames from `51 cc 00 00` records; reconstruct TCP streams before
   parsing; check every length and identifier; keep unknown types unlabelled.
4. Session: follow one UID/RID through LAN request/reply, knocks, path selection, data, alive and
   close, on same-LAN, different-NAT and naturally relayed setups. Confirm channel 0 / datatype 1
   DTLS and read the inner ClientHello/ServerHello without logging credentials.
5. Only after passive results match: controlled loss, delay, NAT remapping and disconnection on
   isolated owner networks. Do not probe public infrastructure with malformed packets.
6. Keep a coverage matrix of catalogue rows, version branches and unresolved fields; a working LAN
   connection does not validate the relay catalogue.
