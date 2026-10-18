# Kalay LAN search and LAN-direct bypass

Part of the [LAN discovery chapter](../lan-discovery.md). This file specifies the Kalay SDK's LAN
search (opcodes 0601 to 0604), which is unrelated to the UDP 4720 scan, and the optional
LAN-direct socket bypass of the P2P tunnel. Labels: [lan-discovery.md: Conventions](../lan-discovery.md#conventions).

## Kalay LAN search: opcodes 0601 to 0604

Basis: static analysis of the Kalay SDK in firmware 9.31 (search sender, packet
handler, LAN handler, reply builders and) and in the
Android SDK library. Firmware 9.75 keeps the opcode compare set 0601 to 0604 and the constants
0x1760, 0x78, 60000 and 10000 in the LAN handler (READ), but the handler is smaller (log strings and
a precheck-failure text are gone). Of the two reply builders, the legacy one (the internal reply builder,
same size in both builds) is a call-for-call match between firmware 9.31 and 9.75, differing only in
rodata/GOT address computations (READ); the current one (the internal reply builder, smaller in 9.75) has
its call sequence preserved apart from one removed debug-log call, matching the handler's own
size shrinkage, and its packet-field construction is now traced: the extended reply's field assignments match 9.31 in both builds (READ; byte map in [lan-discovery.md](../lan-discovery.md)). The 60000 and 10000
constants are not new timers (the 9.31 recycler held them; see
[iotc/index.md: Firmware 9.75 build comparison](../iotc/index.md#firmware-975-build-comparison)). The reply field
layouts in the sections below are verified on firmware 9.31, and the extended reply also on firmware 9.75 (both builds).

This is part of the Kalay IOTC session layer, used during a `REMOTE` connect. It is unrelated to
the UDP 4720 scan. Framing and scrambling are in [iotc/framing.md](../iotc/framing.md); connection use in
[iotc/connect.md](../iotc/connect.md).

### Port and addressing

R31. The search port defaults to **UDP 32761** on both sides; an SDK setter can change it. With
no destination the sender broadcasts on each eligible interface's directed broadcast address;
with a destination it unicasts. READ.

R32. These packets are outside DTLS but carry the legacy IOTC scrambling, which is keyed from the
SDK licence. Offsets below are after unscrambling. READ.

### Header

16-byte legacy IOTC header `H`, little-endian. The body `B` starts at H+16. READ. Only fields
specific to the search are listed; see the IOTC chapter for the rest.

| Offset | Size | Type | Value / meaning |
|---:|---:|---|---|
| 0 | 2 | LE16 | magic `0x0204` (bytes `04 02`) |
| 2 | 1 | u8 | protocol revision 29 (`0x1d`) |
| 4 | 2 | LE16 | body length (72 for requests) |
| 8 | 2 | LE16 | opcode: `0x0601`, `0x0603`, `0x0604` request; `0x0602` reply |
| 10 | 2 | LE16 | route: low byte `0x21` request, `0x12` reply; high flag `0x0200` = refusal |
| 15 | 1 | u8 | search argument from the caller (requests) |

### Request body (0601, 0603, 0604)

| Offset | Size | Type | Meaning | Label |
|---:|---:|---|---|---|
| 0 | 20 | bytes | Target UID; all zero when enumerating | READ |
| 20 | 16 | bytes | zero | READ |
| 36 | 4 | LE32 | SDK version | READ |
| 40 | 8 | bytes | RID: per-attempt random cookie | READ |
| 48 | 4 | LE32 | connect flag: 0 enumerate, 1 precheck, 2 commit | READ |
| 52 | 4 | LE32 | discriminator | READ |
| 56 | 2 | LE16 | requested IOTC port (admission selector) | READ |
| 58 | 8 | bytes | IOTC auth-key bytes (copied from the session's auth key) | READ |
| 66 | 6 | bytes | zero | READ |

Opcode choice: READ.

```text
opcode = 0x0601
if connect_flag == 0 and discriminator given:  opcode = 0x0603
if requested_port != 0:                         opcode = 0x0604   (overrides 0x0603)
```

R33. The device accepts 0603 only with a body of at least 72 bytes and a discriminator equal to
its own local discriminator (1 to 15). READ.

R34. For connect requests the device checks the target UID, the pre-session and RID state, and
the requested port against its accepted-port check. The port is an IOTC admission selector; it
does not ask the tunnel to open an application port such as 4700. READ.

R35. Auth bytes: when the device's auth type is 0, the 8 bytes must equal the device's login auth
data, else result 5. A compatibility path distinguishes empty auth bytes and unsupported key
authentication (results 6 or 7). These 8 bytes are not the LAN lock password, not the 4700
client signature and not the DTLS credentials. READ. The Seestar app passes no authentication
input to its connect call, so it sends no key of its own; it does not derive one from the tunnel
username and password. READ. The Seestar device never sets an eight-byte key either
([sdk-licence.md R46](../../auth/cloud-auth/sdk-licence.md#device-side-sdk-start)). Their value is never published
here.

### Reply body (0602)

Three body sizes are accepted. READ.

| Size | Layout |
|---:|---|
| 36 | UID[20] at 0; sockaddr[16] at 20 |
| 168 | as 36, plus name[129] at 36, padding at 165..167. Old builder: sockaddr holds the **requester's** address |
| 184 | UID[20] at 0; sockaddr[16] at 20, **zeroed**; name[129] at 36; padding 165..167; LE32 SDK at 168; RID[8] at 172; LE32 result at 180 |

sockaddr[16]: LE16 family 2, port in network order, 4 IPv4 bytes, 8 zero bytes. READ.

Result codes (184-byte form). READ.

| Result | Meaning |
|---:|---|
| 1, 7 | accepted: the client may commit |
| 3 | refused |
| 4 | port rejected |
| 5 | wrong auth key |
| 6 | no key authentication |

### Exchange

```text
client                                         device
  |-- 0601/0603 flag 0 (enumerate) or flag 1 ---->|
  |      (broadcast or unicast, UDP 32761)        |
  |<------------- 0602 (UID, RID, result) --------|
  |  UID and RID match a connecting session,      |
  |  result 1 or 7                                |
  |-- 0601 flag 2 (commit) to replying endpoint ->|
  |  client installs direct send path 0,          |
  |  LAN state 6                                  |
```

R36. The client correlates a 184-byte reply by UID and RID with its connecting session. Route
flag `0x0200` also means refusal. Short forms fall back to punch/knock and short-RID handling.
READ.

R37. The device address is the reply's UDP source; the reply's sockaddr is zero or echoes the
requester. A peer cannot steer a client to another address by writing one there. READ.

R38. Timers (Android SDK): LAN search retries every 100 ms; lifetime 60000 ms by default (the
compiled value -1 is replaced), precheck task 100 ms / 30000 ms. LAN and master (server)
searches run in parallel. A session option or zero timeout disables LAN search. The tunnel
connect has its own 30000 ms budget, so the app may give up earlier. READ.

## Optional LAN-direct socket bypass

Basis: static analysis of the Android P2P tunnel library and firmware 9.31 tunnel server
initialization.

When a `REMOTE` session's IOTC path is LAN (mode 2), the P2P tunnel client can carry an
application stream over a direct TCP connection to the device instead of through the tunnel.
The full mechanism — enablement on both sides, the per-connection gate (ready, direct enabled,
port mapping type 1), port verification, the plaintext direct leg and the fallback to tunnel
SETUP — is specified in the P2P tunnel session chapter,
[p2p-tunnel/session.md: LAN-direct bypass](../p2p-tunnel/session.md#lan-direct-bypass). This section records
only that the Kalay LAN search (mode 2) is what makes that path reachable.

Consequence: on a same-subnet `REMOTE` session, control JSON, images, files and RTSP may cross
the LAN in plaintext after a secure setup. The device sees these direct connections as external,
not loopback, so they need the 4700 verification exchange. INFERRED. Whether the login reply's
proxy flag matters is not the client's gate (READ); runtime success and fallback on a given
network are unresolved; see Q29 in [00-overview.md: Open-question register](../../00-overview.md#open-question-register).
