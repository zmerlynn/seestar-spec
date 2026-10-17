# IOTC legacy framing and message catalogue

Part of [Kalay/IOTC session](index.md). This file gives the legacy 16-byte IOTC header, its
scrambling transform, the licence-derived mask, and the byte layouts of legacy control, data,
alive and close packets. Below: UDP datagrams or a TCP byte stream. Above: session behaviour
([session.md](session.md), [connect.md](connect.md)); the newer encrypted envelope is in
[rendezvous-gcm.md](rendezvous-gcm.md). Labels and notation: [index: Conventions](index.md#conventions).

Basis: static analysis of the device library (firmware 9.31) and app library (app 3.3.2).

## Legacy header

All offsets describe bytes **after unscrambling**. The header is little-endian and is not
byte-swapped by the SDK's hton/ntoh helpers. READ.

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 0 | 2 | LE16 | Magic `0x0204` (bytes `04 02`) |
| 2 | 1 | u8 | Protocol revision, generated as `0x1d` (29); distinct from SDK version |
| 3 | 1 | u8 | Flags: bit 0 partial scrambling; bit 1 little-endian sender; bit 3 extended RID |
| 4 | 2 | LE16 | Body length, excluding H |
| 6 | 2 | LE16 | Packet sequence; zero in many control builders, per-channel counter in data |
| 8 | 2 | LE16 | Opcode |
| 10 | 2 | LE16 | Routing word; high byte `0x02` is a refusal flag in knock/LAN replies |
| 12 | 2 | LE16 | Short RID or relay allocation ID (opcode-dependent) |
| 14 | 1 | u8 | IOTC channel |
| 15 | 1 | u8 | Datatype in low two bits (data); search argument (LAN requests) |

R1. Routing low-byte values used by builders: `0x21` client to device, `0x12` device to client,
`0x24` client to server, `0x14` device to server, `0x33` knock exchanges, `0x34` P2P requests,
`0x3f` hello requests, `0x18` master queries. READ. These are observed builder values, not an
established bitfield grammar. INFERRED.

R2. The sender sets flag bit 1 (`0x02`). In partial mode it scrambles `min(total, 64)` bytes,
otherwise the whole packet. READ.

Synthetic example (plaintext, before scrambling): a direct client-to-device data packet with an
extended RID, channel 0, datatype 1, carrying a 40-byte DTLS record.

```text
04 02 1d 0b 34 00 05 00  07 04 21 00 11 11 00 01   H: magic, rev 29, flags 0x0b, len 52,
                                                      seq 5, opcode 0407, route 21,
                                                      H+12 = RID low 16 bits, ch 0, type 1
0c 00 00 00 11 11 11 11  22 22 22 22               LE32(12), RID8 (synthetic)
17 fe fd ...                                        DTLS record, 40 bytes
```

### UDP reception

R3. A UDP receiver requires at least 16 bytes, unscrambles H first, checks the magic, and requires
`received_length == 16 + H.length` and total length at most **1416** (`0x588`). It then
unscrambles all of B, or only its first 48 bytes when flag bit 0 is set, and dispatches. Bad
lengths or magic are dropped. READ.

### TCP reception

R4. A TCP receiver accumulates 16 header bytes, unscrambles them, reads the body length,
accumulates the body, and processes surplus bytes as further packets. On a bad magic it shifts
by one byte and searches again. The same 1416-byte limit and scrambling apply. There is no extra
length prefix. READ. Datagram boundaries and TCP read boundaries are not interchangeable; a
receiver MUST frame TCP by the header length. INFERRED.

### Revision and flag bits on receive

The generic UDP and TCP receivers check only the magic, the length and flag bit 0. READ (device
and app libraries). Later handling (READ):

| Header field | Device library | App library |
|---|---|---|
| Revision (byte 2) | Not checked generically. LAN-search reply handling compares it with 23 (auth-key support) and 7 (refusal form) and stores it per session | Compared with 7 in the same handling and logged |
| Flag bit 0 | Selects partial unscrambling | Same |
| Flag bit 1 | Stored per session; never causes byte swapping (the header byte-order helpers are empty) | Not tested |
| Flag bit 2 | Not tested | Relay-forwarded data `0503` and one other path: the packet is logged and **dropped** |
| Flag bit 3 | Selects the extended-RID lookup; not checked against the opcode. Extended forms add body-length minimums | Same |
| Flag bits 4–7 | Not tested | Not tested |

R4a. A sender MUST send revision 29 and MUST NOT set flag bits other than 0, 1 and 3. A receiver
SHOULD ignore flag bits 2 and 4–7 and SHOULD NOT reject a packet on its revision alone; the
revision only selects reply forms in LAN-search handling. A receiver MUST NOT
byte-swap on flag bit 1. INFERRED (policy, from the READ table; the official app's bit-2 drop is
a client quirk, not a sender permission).

## Ports and maximum sizes

R5. Maximum IOTC packet 1416 bytes; maximum application bytes per data packet 1388. READ.
Port numbers are in [connect: Endpoint discovery](connect.md#endpoint-discovery).

## Scrambling

### Key

R6. The 16-byte scrambling key `K` is a fixed 16-byte ASCII constant built into the SDK (the first
half of a 32-byte phrase), XORed byte-wise with the 16-byte licence mask when the mask is
obtained. With no mask, the constant is used as is. READ. The phrase is reproduced in
[embedded-constants.md: Legacy transform phrase](../../auth/cloud-auth/embedded-constants.md#legacy-transform-phrase).
The app library rebuilds the same phrase by XORing two embedded arrays. READ.

### Forward transform

R7. For each full 16-byte block in the scrambled portion, independently (READ):

1. Read four LE32 words; rotate each right by 1, 5, 9, 13 bits respectively.
2. XOR byte `i` with `K[i]`, `i = 0..15`.
3. Permute: `out[i] = in[P[i]]`, `P = [11,9,8,15,13,10,12,14,2,1,5,0,6,4,7,3]`.
4. Read four LE32 words; rotate each right by 3, 7, 11, 15 bits.

R8. For a final residual of `r` bytes: XOR byte `j` with `K[j]` (key index restarts at 0), then
permute only when `r` is 2, 4 or 8, with `2:[1,0]`, `4:[2,3,0,1]`, `8:[7,4,3,2,1,6,5,0]`. Other
residual sizes are not permuted. Bytes beyond the scrambled length are copied unchanged. There
is no padding, IV, chaining, checksum or tag. READ.

### Inverse transform

R9. Full block: rotate left 3, 7, 11, 15; apply `P` (self-inverse); XOR `K`; rotate left 1, 5, 9, 13.
Residual: permute first, then XOR. READ. An internal guard value seen in these calls is an API
check, not a key or magic. READ.

R10. Synthetic round-trip tests of this transcription exist in the evidence; they show internal
consistency only. Compatibility needs comparison with real library traffic. INFERRED / unresolved.

### Mask from the licence

R11. The licence is Base64. After decoding (READ):

1. The first LE32 is a version, 1.
2. The next RSA-block-sized chunk is processed with an embedded **1024-bit RSA public key** (the
   licence key), using raw RSA (see R12).
3. The first 32 recovered bytes are a repeating XOR mask over the remaining bytes; this recovers
   a JSON string.
4. SHA-256 of the JSON string (up to NUL), with digest byte 0 overwritten by `0x11`, must equal 32
   bytes recovered by the RSA step.
5. The JSON MUST contain `realm`. A `keyMask` member is accepted only if it Base64-decodes to
   exactly 16 bytes; that is the scrambling mask. Optional `standalone` and
   `nebulaDomainFromLicense` members are read. Without `keyMask` the mask stays zero.

The licence, the recovered JSON and the mask are secrets of the account. Implementers obtain the
licence at runtime from the cloud ([cloud-auth](../../auth/cloud-auth.md)) and MUST NOT publish it
or values derived from it. INFERRED.

R12. The RSA helper zero-extends its input to whole RSA blocks and uses no padding (OpenSSL
"no padding" mode): no PKCS#1 v1.5 or OAEP block is built. READ. The app library uses the same
wrapper with a separate embedded **2048-bit** master public key: an 88-byte master request is
followed by 168 zero bytes to make one 256-byte block (zeros after, not before). READ.

## Common field types

R13. `sockaddr16` in legacy builders: LE16 family 2 at +0, port in network order (BE16) at +2,
IPv4 octets at +4, 8 bytes zero for locally built addresses. Copied received sockaddrs are not
necessarily normalized in the last 8 bytes. READ. Receivers SHOULD ignore those 8 bytes. INFERRED.

R14. `authkey[8]`: optional 8-byte IOTC auth field, or zeros. It is not the tunnel password.
READ. "SDK" fields are the LE32 SDK version (e.g. `0x04030603` device library). READ.

## Generated control packets

Offsets are body (`B`) offsets. Source builders are in the device library. READ unless noted.

| Opcode | Route | Body |
|---|---|---|
| `1007` master query | `18` | 38: UID20 @0, realm[16] @20, u8=6 @36, u8 role @37 |
| `8003` hello | `3f` | 8: LE32 hello serial @0 (increments), LE16 instance ID @4, u8 argument @6, 0 @7 |
| `0120` registration | `14` | 117, see R15 |
| `0122` compact registration | `14` | 32: UID20, authkey[8] @20, LE32 Unix seconds @28 |
| `0124` sleep registration | `14` | 32: UID20, authkey[8] @20, LE32 sleep serial @28 (copied only for input type 3, else 0) |
| `0211` precheck 1 | `24` | 20: UID20 |
| `0214` precheck 2 | `24` | 32: UID20, reserved[4] @20, authkey[8] @24 |
| `0203` P2P request | `34` | 96 or 272: UID20, four sockaddr16 @20, RID8 @84, LE32 NAT @92; long form zero @96..263, authkey[8] @264 |
| `0205` relay request | `24` | 20 for peer protocol <10, else 32: UID20, RID8 @20, LE32=60000 @28 |
| `0207` relay request 3 | `24` | 36: UID20, RID8 @20, LE32=60 @28, LE32=5 @32 |
| `020a` relay request (auth) | `24` | 48: UID20, RID8 @20, LE32=60 @28, LE32 @32 (5 or 0 by builder), LE16 requested port @36, zero[2] @38, authkey[8] @40 |
| `0209` relay session-info request | `24` | 20 for peer protocol <10, else 44: UID20, RID8 @20, LE32 argument low byte @28, LE32 SDK @32, LE32 protocol=29 @36, LE32 NAT @40 |
| `030c` relay info ACK | `24`/`14` | 28: UID20, RID8 @20; H+12 is relay ID |
| `0103` / `010c` relay knock response | `14` | 24 or 32: UID20, LE32 result @20, optional RID8 @24 (`010c`: extended) |
| `0301` punch-to | `21` | 36: UID20, sockaddr16 @20 (not the larger server punch with the same opcode) |
| `0401`, `0403` knock | `33` | 36: UID20, RID8 @20, LE16 argument @28 (0 for `0401`), zero[2] @30, LE32 SDK @32 |
| `0402`, `0405` knock response | `33` (+`0200` refusal) | 24 (old peer) or 36: UID20, RID8 @20 (old: first word only), LE16 result/port @28, reserved[2] @30, LE32 SDK @32 |
| `0404`, `0406` knock final | `33` | 24 (old) or 36: UID20, RID8 @20, LE32 response argument @28, LE32 SDK @32; H+6 carries a session counter |
| `0601`, `0603`, `0604` LAN request | `21` | 72, see R17 |
| `0602` LAN response | `12` | 168 (old) or 184 (new), see R18 |
| `0228` wake-up | `24` | 32: UID20, ASCII `WakeUpMsg!!!` (12 bytes, no NUL) @20 |
| `0231` device status query | `24` | 28: UID20, authkey[8] @20 |
| `0801` connect success | `24` | 40: UID20, 16-byte selected send-path sockaddr @20, u8 device NAT @36, u8 client NAT @37, u8 mode @38, 0 @39 |
| `0804` connection result report | `24` | 528 (total 544): UID20 @0, statistics body unspecified |

R15. Registration `0120` body (READ):

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 20 | UID20 |
| 20 | 4 | LE32 = 2 (unit count) |
| 24 | 4 | Unit 1 header: u8 type=1, u8 reserved, LE16 length=36 |
| 28 | 16 | sockaddr16 |
| 44 | 4 | LE32 SDK |
| 48 | 4 | LE32 NAT |
| 52 | 8 | authkey[8] |
| 60 | 4 | LE32 timestamp |
| 64 | 4 | Unit 2 header: u8 type=2, u8 reserved, LE16 length=49 |
| 68 | 49 | SDK version string including NUL |

R16. The device sends compact `0122` while the tracked login information is unchanged, and full
`0120` otherwise. READ.

R17. LAN request (72 bytes, READ): UID20 @0 (zeros when enumerating), zero @20..35, LE32 SDK @36,
RID8 @40, LE32 connect flag @48, LE32 search discriminator @52, LE16 requested port @56, auth[8]
@58, zero @66..71. Opcode `0603` is chosen when the connect flag is 0 and a discriminator is given;
`0604` supersedes it when the requested port is nonzero; otherwise `0601`. H+15 carries the
caller's first argument.

R18. LAN response (READ): UID20 @0, sockaddr16 @20, device name[129] @36, padding @165..167. The old
builder sends 168 bytes with the requester address in the sockaddr. The new builder zeros the
sockaddr and adds LE32 SDK @168, RID8 @172, LE32 result @180 (184 bytes). Receivers also accept an
oldest 36-byte form (UID + sockaddr).

R19. The 16 bytes at `0801` body @20 are the IOTC-serialized socket address of the connection's
currently selected send path (the negotiated peer endpoint of the winning connection mode), copied
verbatim from per-session connection state; they are not key material. The builder fills @36 from the
stored peer NAT byte, @37 from the live local NAT type (`IOTC_Get_Nat_Type`), @38 from the connection
mode and @39 with zero. READ (app library, SDK 4.3.8). Some argument meanings in relay/knock builders
still have no assigned semantics (positions and widths READ). unresolved.

## Receive catalogue

Minimum lengths are parser guards, not full validation. Fields not listed are opaque. READ from the
device library dispatcher unless noted. The app library recognizes `0103, 010b, 0121, 0125, 0126,
0206, 020b, 0212, 0215, 0216, 0301, 0303, 1008` only to log and return; it handles the modern record
replacements separately ([rendezvous-gcm.md](rendezvous-gcm.md)). READ.

| Opcode(s) | Meaning / fields / minimum body |
|---|---|
| `0008` | Unlicensed UID: UID20; ≥20; UDP source must be a known master. Sets login/connect failure. |
| `000a` | No TCP support: UID20; ≥20. |
| `0103`, `010b` | Relay knock: UID form ≥20; RID form at ≥28. Extension semantics unresolved (server-side). |
| `0121` | Registration reply: ≥28; UID20, u8 server type @20, LE32 logged value @24. Updates login status. |
| `0123` | Registration-alive reply: ≥40; UID20, observed sockaddr16 @20, echoed LE32 timestamp @36. |
| `0125` | Sleep-registration reply: ≥20, UID20. Only source and UID are used: after checking a known P2P-server source and the local UID, the device calls its sleep callback with the source IPv4/port. |
| `0126` | Notify device to register: ≥20, UID20. Resets server registration state; starts a 1000 ms retry task with 6000 ms lifetime if absent. |
| `0206`, `020b` | Relay request reply: ≥24, UID20 and signed LE32 result @20; ≥32 adds RID8 @24. |
| `0208` | Relay request reply 2: ≥32; UID20, signed result @20, RID8 @24. |
| `0212`, `0215`, `0216` | Precheck reply: ≥44; UID20, LE32 seconds @20, opaque @24..35, LE32 NAT @36, LE32 SDK @40; ≥48 adds auth-use byte @44. |
| `0227` | Device not logged in: UID20, ≥20. |
| `0229` | Device asleep: 24 bytes, or ≥28 with LE32 wait seconds @24. |
| `022e` | Authorization failed: UID20, LE32 result @20; ≥24. |
| `0232` | Device-status reply: ≥28; UID20, two LE32 @20/@24, copied verbatim into connection state; sets local state `0x18`. The `IOTC_Check_Device_Online` query reads them back: @20 is a status bitfield (bit 0 set = device reachable); @24 is an ordering magnitude, the maximum of which across the device's connection entries is selected and returned as the reported online value. The absolute unit of @24 (sequence vs time) is unresolved (server-side). READ (app library, SDK 4.3.8) for the rest. The device-side library's `IOTC_Check_Device_OnlineEx` uses the same reader logic on its own copy of the entry: a status bitfield at @20 (bit 0 = reachable) and the maximum seen value of the field at @24. READ (device side). In firmware 9.75 this device-side function gained a new early exit, returning -12 when a connection-state byte it checks is 0 or 3; this is an internal short-circuit and does not change the wire format above. READ (firmware 9.75). |
| `0301` | Server punch instruction: UDP from a known P2P server; >115 and >291 select larger forms; see R22. |
| `0303` | Relay session information: ≥56 old form, ≥80 new; see R21. |
| `0401`/`0403`, `0402`/`0405`, `0404`/`0406` | Knock, knock response, knock final: 24-byte old or ≥28 extended. |
| `0407`, `0408` | Direct data ([Data, alive and close packets](#data-alive-and-close-packets)). |
| `0417`, `0418` | Direct close ([Data, alive and close packets](#data-alive-and-close-packets)). |
| `0427`, `0428` | Direct alive ([Data, alive and close packets](#data-alive-and-close-packets)). |
| `0501`, `0503` | Relay-forwarded data, server to device / server to client. |
| `0511`, `0513` | Relay close; exactly 8 body bytes selects RID lookup, else relay ID/address. |
| `0521`, `0523` | Relay alive; extended flag needs ≥8 bytes RID, else relay ID/address. |
| `0601`, `0604` | LAN request; validated and answered. |
| `0603` | LAN request with discriminator: ≥72 and B+52 equal to the local discriminator (1..15). |
| `0602` | LAN response: 36, 168 or ≥184 bytes. |
| `1008` | Master reply: ≥56; UID20, observed sockaddr16 @36, LE16 unit count @54, units @56 (R20). |
| `1009` | Alternate master response: NAT-tracker signal. |
| `8004` | Hello reply: ≥16 observed sockaddr16 @0; ≥24 adds LE32 serial @16, LE16 instance ID @20. |
| `8005` | Alternate hello response: NAT-tracker signal; same optional fields. |

R20. Master unit list (`1008`; also used by modern `100c`): each unit is `{u8 type, u8 reserved,
LE16 length, data[length]}`. Type 1 data: VID, PID, GID as three LE16. Type 2: consecutive
sockaddr16 entries (count = length / 16). Truncated units are rejected, address+port duplicates
dropped. UID must match the logged-in device or a connecting session. READ.

R21. Relay session information `0303` (READ):

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 20 | UID20 |
| 20 | 4 | LE32 relay allocation ID (low 16 bits go to H+12) |
| 24 | 16 | Client sockaddr16 |
| 40 | 16 | Device sockaddr16 |
| 56 | 8 | RID8 (≥80 form) |
| 64 | 4 | LE32 client SDK |
| 68 | 4 | LE32 device SDK |
| 72 | 4 | LE32 client protocol revision |
| 76 | 4 | LE32 device protocol revision |
| 80 | 4 | LE32 client NAT (≥88) |
| 84 | 4 | LE32 device NAT (≥88) |

Each endpoint uses the opposite endpoint's address, version and NAT. Handling installs path 2 (UDP
relay) or 3 (TCP relay); the extended client path ACKs with `030c`; the old form switches to short
RID. READ.

R22. Server punch `0301`, smallest form: UID20 @0, target sockaddr16 @20. The receiver finds the
session by UID and sends a knock to the target; a client switches to short RID. The larger forms
carry UID20 @0, primary WAN sockaddr @20, four LAN sockaddrs @36, RID8 @100, NAT words @108/@112,
additional WAN array @116. Measured from H, each sits four bytes before its modern `030d`
counterpart ([rendezvous-gcm: Control layouts](rendezvous-gcm.md#control-layouts)). The additional WAN array is
eight `sockaddr16` slots at body @116..243: the parser walks them in 16-byte steps, stops at the
first zero IPv4, dedupes by IPv4+port and keeps at most eight WAN endpoints in total (the primary
plus up to seven more), matching modern `030d`. Bytes past @243 are ignored. The two larger forms
differ only in how much of this array is present. READ.

R23. Signed results in extended relay request replies (wire values, not public SDK error codes):

| Value | Meaning |
|---:|---|
| 0 | Ready |
| -1 | Device refused |
| -2 | Server refused |
| -3 | No such UID |
| -4 | Another relay request active |
| -5 | Device lacks server-relay support |
| -6 | Multiple login |
| -7 | Received, pending |
| -8 | Possibly asleep |
| -9 | Requested port rejected |
| -22 | Auth key rejected |
| -23 | Old version, no auth |

READ.

R24. Hello reply length (app library): the LE16 length is compared with 24; 16 to 23 parses the
sockaddr only; below 16 is an error exit. The client therefore accepts a short reply without the
serial/instance echo, and the 24+ path does not compare the latest serial. The compared value is the body-length field at
header offset 4, which excludes the 16-byte header H; the 24 and 16 thresholds are body lengths.
READ. Whether any server actually sends the short form needs server evidence. unresolved.

## Data, alive and close packets

| Packet | Direct opcodes / route | Relay send / route | Relay receive | Extended body | Short form |
|---|---|---|---|---|---|
| Data | `0407` C→D `21`, `0408` D→C `12` | `0504` C `24`, `0502` D `14` | `0503`, `0501` | `LE32(12) RID8` + data | data only; H+12 short RID |
| Alive | `0427` `21`, `0428` `12` | `0524` `24`, `0522` `14` | `0523`, `0521` | RID8 only (length 8), flag `08` | empty; H+12 short RID |
| Close | `0417` `21`, `0418` `12` | `0514` `24`, `0512` `14` | `0513`, `0511` | RID8 (length 8) | empty |

R25. Data: at most **1388** application bytes; per-channel sequence at H+6; channel at H+14;
datatype (masked with 3) at H+15. In extended format set flag `0x08` and prepend `LE32(12) ||
RID8`; H.length is `12 + data_length`. On direct paths the app's writer also copies the low 16
bits of the first RID word to H+12, in extended format as well as short. Relay paths put the
relay ID at H+12. READ.

R26. Datatype 0 is ordinary data; datatype 1 is DTLS ([dtls: Encapsulation and role](dtls.md#encapsulation-and-role)).
READ.

R27. Alive has **no** `LE32(12)` prefix; its extended body is the bare RID8. READ.

R28. Direct close receivers fall back to peer address/port when H+12 is zero. READ.

## Raw NAT keepalive

R29. The device's keep-NAT task (every 10000 ms) sends the four bytes `cc aa ab ab` to eligible
listed P2P servers (UDP available, nonzero port, TCP fallback off). It has neither the legacy
header nor the modern envelope; no reply is established. A client need not send it. READ.
