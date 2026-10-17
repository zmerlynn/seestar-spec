# Cloud auth: SDK hand-off and licence envelope

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file covers how
the allocation from [`online-link`](http-api.md#allocation-online-link) is handed to the
ThroughTek SDK, the structure of the SDK licence, and the device-side SDK start. The messages the
SDK then exchanges with masters and P2P servers are in [master-legacy.md](master-legacy.md) and
[master-record.md](master-record.md); the tunnel itself is in [P2P tunnel](../../transport/p2p-tunnel/index.md).

Basis: static analysis of app 3.3.2 (Java layer, SDK 4.3.8 libraries), firmware 9.31 (SDK
4.3.6) and firmware 9.75 (SDK still 4.3.6, same version word and version strings as 9.31; READ in
both builds). Statements are firmware 9.31 unless tagged.

## Client hand-off

Order of operations in the app's connection engine (READ):

1. Set the IOTC session-alive timeout to 30 s.
2. Install the licence: `TUTK_SDK_Set_License_Key(sdkLicenseKey)`. The return value is logged
   only; the app does not abort on failure here.
3. On the first connection only, initialize the tunnel agent with `P2PTunnelAgentInitialize2(4, 1)`.
4. Clean up stale port mappings and channels.
5. Connect the primary and then the secondary tunnel with
   `P2PTunnelAgent_Connect_Ex(deviceUid, callback, null)`. The callback fills the account and
   password output buffers with `username` and `password` from the allocation.
6. On a negative result or cancellation, clean up. On -30002 (port in use), wait 250 ms and retry
   the sequence once if the attempt is still current.

R40. A client MUST install the licence before the SDK connects, and SHOULD stop if installation
fails. INFERRED (the app only logs the result and continues; the device-side wrapper aborts, [Device-side SDK start](#device-side-sdk-start)).

R41. Inside the SDK, the tunnel connect first establishes an IOTC session by UID, with a null
authentication input to the rendezvous. Only after that succeeds does it create the RDT channel
(30 000 ms timeout) and run the tunnel authentication callback. READ. Therefore the tunnel
username/password plays no part in master, P2P-server or relay authorization.

SDK global error codes (READ): 0 success, -1001 already initialized, -1002 invalid argument,
-1003 out of memory, -1004 invalid licence, -1005 no licence, -1006 unsupported. The app's own
-10086 (cancel) and -10087 (timeout) are workflow codes, not wire values. READ.

## Licence envelope

The licence string `sdkLicenseKey` is opaque to the app and is decoded by the SDK. Both client
and device SDKs use the same algorithm. READ. No licence value is given in this specification.

The string is Base64. Decoded layout (READ):

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 0 | 4 | LE32 | Envelope version; MUST be 1 |
| 4 | 128 | bytes | Block for a raw RSA public operation with the SDK's embedded licence key |
| 132 | n > 0 | bytes | JSON payload, XOR-obfuscated |

Validation (READ):

1. Reject if version ≠ 1 or the payload length is not positive.
2. Apply the raw RSA public operation (no padding scheme: OpenSSL padding value 3,
   `RSA_NO_PADDING`, as named in OpenSSL's public header) to the 128-byte block, using the
   licence-verification public key, a 1024-bit RSA key embedded in the SDK libraries. Call the
   128-byte result `D`.
3. XOR every payload byte `i` with `D[i mod 32]`.
4. Compute SHA-256 over the de-obfuscated payload up to its first NUL (a NUL is implied after the
   last byte). Set digest byte 0 to `0x11`.
5. Accept only if all 32 bytes equal `D[0..31]`.

The public key is reproduced in [embedded-constants.md: Licence-verification public key](embedded-constants.md#licence-verification-public-key).

R42. A licence is therefore produced only by a holder of the matching private key. A stand-in
device or client cannot mint one; it MUST use a licence issued by the service. INFERRED.

### Licence JSON

Installing a licence first clears any previous validity, realm, key mask and standalone
overrides. The JSON then supplies (READ):

| Member | Type | Required | Meaning |
|---|---|---|---|
| `realm` | string | yes | Realm used in master host names and in query/register messages |
| `nebulaDomainFromLicense` | boolean | no | Selects licence-supplied Nebula gateway names (see below); not used by the Seestar path |
| `keyMask` | string (Base64) | no | Must decode to exactly 16 bytes; masks the legacy transform key. Absent: all zero |
| `standalone` | object | no | Region name to master host name; the first ten entries are copied (see below) |

Successful parsing marks the licence valid. READ.

`standalone` entries are taken in the SDK JSON object iterator's order, and only the first ten
are examined; later entries are neither copied nor validated. Every examined entry needs a key
name and a string value, otherwise installation fails with -1004 and the licence stays invalid.
Each slot holds a region name and a host name of up to 128 characters, copied without a length
check. READ (device library). The iterator order is document order: the SDK's embedded JSON
parser adds each object member as it is parsed, its object table appends each new key at the
tail of an ordered list, and the iterator walks that list from the head. A duplicate key keeps
the position of its first occurrence and takes the last value. READ (device library). Lookup needs a valid licence (-1005), scans the slots in order, stops at the first empty
region name, compares region names exactly and returns the first match; no match gives -1002.
READ. A licence with more than ten entries or with region or host names over 128 characters is
therefore outside the interoperable range. INFERRED.

Explicit `null` members (READ in the device library; that the SDK's JSON parser stores `null` as
a present member without a value is INFERRED from its conventions). The member lookup reports
such a member as found, and every typed read of it fails with the parser's internal error
-40002, which the installer handles per member:

| Member | `null` | Wrong type |
|---|---|---|
| `realm` | -1004, licence invalid | Converted to text; INFERRED |
| `nebulaDomainFromLicense` | Same as absent (false); the read result is ignored | Same as absent |
| `keyMask` | Same as absent (all-zero mask) | Converted to text, which does not decode to 16 bytes: -1004 (INFERRED) |
| `standalone` | Same as absent (no entries) | Non-object: skipped, same as absent; `{}`: no entries |
| a `standalone` entry value | -1004 | See the entry rule above |

R43a. A licence issuer SHOULD omit optional members rather than send `null`, and MUST send
`realm` as a string. A client that parses licences itself SHOULD treat `null` as absent for
`keyMask`, `standalone` and `nebulaDomainFromLicense`, and reject the other cases above. INFERRED.

`nebulaDomainFromLicense` is read only when building a Nebula gateway host name. When false the
name is built from the region and fixed vendor suffixes. When true the stored region's
`standalone` entry is used, falling back to a built name on a miss. READ (device library). No
caller of that builder was found in the device library. In the app libraries the builder is
exported only by the global SDK library and has no callers at all: it is not imported by the IOTC
or P2P-tunnel libraries and has no internal caller or address-taken reference, so the app never
builds Nebula gateway names from `nebulaDomainFromLicense` and the Seestar connection path does not
reach it. READ (app library, SDK 4.3.8). A Seestar client MAY ignore the flag. INFERRED.

R43. Realm reads are fixed width: the realm is copied with `strncpy` semantics into 16 bytes,
NUL-padded when shorter and truncated **without** a terminator when 16 bytes or longer. READ.
Wire realm and UID fields MUST be handled as fixed-width byte fields.

R44. Reading the key mask needs a destination of at least 16 bytes (-1002 otherwise) and a valid
licence (-1005 otherwise). The mask is 16 contiguous bytes. READ.

## Device-side SDK start

The device's tunnel server wrapper (READ, firmware 9.31 64-bit build; for the 32-bit build only
step 5 was compared, and it matches):

1. Installs its licence and **aborts on a nonzero result** (unlike the app).
2. Sets the session-alive timeout to 30 s.
3. If the tunnel server is already initialized, de-initializes it first (aborting on error),
   then initializes it with `P2PTunnelServerInitialize2(64, 1)`. Firmware 9.75 (64-bit build, READ)
   adds a retry: when that initialization returns -30007 (already initialized), the wrapper logs it,
   de-initializes the tunnel server and retries the initialization once; if the de-initialization
   fails it aborts. The 32-bit build was not confirmed beyond string presence.
4. Registers a port-verification callback and stores the tunnel account and password.
5. Starts the tunnel server with its UID and the authentication and tunnel-information
   callbacks; this performs a plain IOTC device login `IOTC_Device_Login(UID, 0, 0)`.

R45. The tunnel authentication callback compares the client's account with the stored account
and supplies the stored password. It has no time or one-use check. READ. This is local behaviour,
not a lifetime contract for the credentials.

R46. The SDK also has an extended device login taking a 16-byte structure: LE32 size (16), LE32
auth type (0), eight alphanumeric auth-key bytes; a bad structure, type or key returns -46. The
key can later be changed, which triggers re-registration. READ. The normal Seestar start uses
the plain login, so a stand-in device MUST NOT assume the eight-byte auth key is active.
INFERRED. The Seestar imager never calls the extended login or the key-update entry, and SDK
initialization clears the login input, so the key is unused in this build. READ.

R46a. Origin of the device's licence and tunnel account. The device holds no tunnel account or
password as a local file or embedded constant. They arrive at run time in a `p2p_message` command
(the `p2p_init` action) on the device's cloud remote link, the link that
[`remote_join`](../../../docs/control/methods/remote_join.md) sets up. The imager reads the
members `deviceUid`, `username`, `password`, `conId` and `srcId` from that message and starts the
tunnel server with that account (steps 1 to 5 above). READ (both firmware versions). The licence
differs by version:
- Firmware 9.31: the imager also reads the member `sdkLicenseKey` from the message and installs
  that licence. READ.
- Firmware 9.75 (64-bit build, READ; the 32-bit build has the same change, handler parity beyond
  that not confirmed): the handler no longer reads `sdkLicenseKey`. It builds the licence from a
  licence envelope embedded in the firmware (a Base64 string in the read-only data of the imager;
  its value is not given here; it is a 220-character string, and the cloud-side licence it is derived
  from is not given either), used as the default when `changSdkLicenseKey` is absent (INFERRED), and an optional string member `changSdkLicenseKey` of the message
  replaces it. A non-string `changSdkLicenseKey` is rejected with a log message and the
  initialization fails. A 9.75 device therefore starts the tunnel server with a licence the cloud
  did not have to send. Whether the cloud still sends `sdkLicenseKey` to 9.75 devices, and what the
  embedded default is bound to, are unresolved (server-side); the validation rules of [Licence envelope](#licence-envelope)
  apply to either source. A client or cloud stand-in MUST NOT rely on 9.75 devices honouring
  `sdkLicenseKey`.

Only the licence-verification material is a fixed SDK constant
([embedded-constants.md](embedded-constants.md)). How the cloud derives the other values is
unresolved (server-side).

R46b. Optional send-rate members of `p2p_init` (firmware 9.75, 64-bit build, READ). After the
tunnel server has started, the message may carry `rate` (a positive integer in KiB/s, at most 2097151) and
`rateLimit` (a boolean). The imager hands them to its internal `set_send_rate` command (type 5), which
converts `rate` to bytes per second by a left shift of 10. The downstream image-send limiter then accepts
65536 to 67108864 bytes per second. A failure to dispatch is logged only. The `remove` form is not a
`p2p_init` member: `remove` is a separate cloud command (type 3). Command types, validation texts and the
other `p2p_init` actions are in [device-cloud-link.md R46g to R46j](device-cloud-link.md#remote-commands).
See [media/image-sockets.md](../../media/image-sockets.md) for the limiter. The unit is KiB/s (value times
1024), not decimal kB/s.

R46c. Relay mode (firmware 9.75, 64-bit build, READ). A separate cloud command (type 6) sets a boolean
`isRelayMode`. The effective limiter state is the configured `rateLimit` AND the relay flag; it is applied to the
image-send limiter and to the HTTP download flag file, with rollback if the file write fails. The relay flag
is set 60 s after a P2P connect from whether the connection's NAT mode is `RelayMode`, and cleared when the P2P
session disconnects, before the idle status is reported ([device-cloud-link.md R46i](device-cloud-link.md#remote-commands)).
The 32-bit build contains the same strings; its logic was not diffed.
