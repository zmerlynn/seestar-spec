# Cloud authentication and relay authorization

This chapter covers how a remote client is authorized to reach a Seestar through the cloud: the
ZWO HTTP calls that allocate a remote session, the hand-off of that allocation to the ThroughTek
(Kalay/IOTC) SDK, the SDK licence, and the SDK's own master, P2P-server and relay authorization
messages. Above it sits [account login](account-login.md), which supplies the ZWO token. Below it
sit the [Kalay/IOTC session](../transport/iotc/index.md) (rendezvous, records, GCM
contract) and the [P2P tunnel](../transport/p2p-tunnel/index.md) (port mappings, tunnel login).

App names: the Seestar app calls the remote-access feature that these files describe “Telescope
Network” (also “Remote Connection”): joining a device to it, choosing a remote location, and
connecting to a joined device from anywhere. Names are the English strings of iOS app 3.4.0; links
are READ (app call sites) unless marked.

The chapter is split into these files:

| File | Content |
|---|---|
| [cloud-auth/http-api.md](cloud-auth/http-api.md) | ZWO HTTP authorization, session allocation (`online-link`), stop, reports, device list, cloud error codes, observed single-session behaviour, optional remote-feature catalogue |
| [cloud-auth/sdk-licence.md](cloud-auth/sdk-licence.md) | Java-to-native hand-off, SDK licence envelope, device-side SDK start |
| [cloud-auth/master-legacy.md](cloud-auth/master-legacy.md) | Master host discovery, legacy packet header and transform, legacy master query, device registration, other legacy authorization messages |
| [cloud-auth/master-record.md](cloud-auth/master-record.md) | Record-based (encrypted) master query, server key agreement, device registration record, precheck |
| [cloud-auth/relay.md](cloud-auth/relay.md) | Relay authorization and allocation, legacy and record forms, result codes, alerts |
| [cloud-auth/device-cloud-link.md](cloud-auth/device-cloud-link.md) | The device's own cloud link (MQTT), the `remote_*` RPCs, remote command types and `p2p_init` actions, P2P status report, P2P monitor and occupy timers |
| [cloud-auth/embedded-constants.md](cloud-auth/embedded-constants.md) | Fixed SDK constants needed for interoperability: licence and master-query public keys, legacy transform phrase, master host-name suffixes |
| [cloud-auth/state-timers.md](cloud-auth/state-timers.md) | End-to-end state, retries, timers, API error mapping, teardown |

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients (and stand-in devices where a sentence says so). Sentences about what "the app", "the
SDK" or "the device" does are descriptions.

Every claim carries a label (see `CONVENTIONS.md`):

- **READ**: seen by static analysis of the Android app 3.3.2 (Java layer and its bundled
  ThroughTek libraries, SDK 4.3.8) or of firmware 9.31 (the imager, SDK 4.3.6; 64-bit
  build unless stated, 32-bit build noted where compared). It says what the code does, not what
  the cloud accepts.
- **OBSERVED** (date): seen in a live session. The device firmware in those sessions was not
  matched to 9.31.
- **INFERRED**: an interpretation or consequence, not seen directly.
- **unresolved**: not established either way.

Integers are little-endian (LE) unless marked BE. Offsets are byte offsets. "SDK" means the
ThroughTek IOTC/P2PTunnel libraries. Android ("client") SDK 4.3.8 and device SDK 4.3.6 do not
share an identical message catalogue (READ); each table says which build it describes.

INFERRED — Coverage: the material supports an implementation of the cloud calls, the licence
decoder, master name construction, the legacy transform and several authorization exchanges. It
does not yet support every accepted message. Reply fields of unknown meaning, compact address
encodings and catalogue completeness are noted where they occur and listed in [Open questions](#open-questions). Missing fields MUST NOT be filled by
analogy to another SDK release.

## Credentials and where they come from

A client meets four distinct secrets. They MUST NOT be confused or substituted for each other.

| Secret | Obtained from | Used for | Detail |
|---|---|---|---|
| ZWO token | [account login](account-login.md) | `Authorization` header of ZWO HTTP calls | [http-api.md](cloud-auth/http-api.md) |
| SDK licence (`sdkLicenseKey`) | `online-link` reply | Installed in the SDK before connecting; yields realm and a 16-byte key mask | [sdk-licence.md](cloud-auth/sdk-licence.md) |
| Tunnel username/password | `online-link` reply | P2P tunnel authentication callback, after rendezvous | [sdk-licence.md](cloud-auth/sdk-licence.md) |
| IOTC eight-byte auth key | Not set on Seestar: the device uses the plain login and the app connects with no authentication input | Optional key in register, precheck and relay messages | [master-legacy.md](cloud-auth/master-legacy.md) |

R1. The tunnel username/password is not the IOTC eight-byte auth key and is not fed into the
rendezvous key. READ.

R1a. In firmware 9.31 the device receives its licence and tunnel username/password from the cloud
at run time, in a `p2p_message` command on its cloud remote link, and stores none of them locally.
In firmware 9.75 the licence defaults to one embedded in the firmware and the message carries only
an optional `changSdkLicenseKey` override; the tunnel username/password still arrive in the
message. The Seestar
firmware never sets the eight-byte auth key. READ. See
[sdk-licence.md R46 and R46a](cloud-auth/sdk-licence.md#device-side-sdk-start).

R5. Three embedded SDK constants are needed for interoperability: the licence-verification public
key (RSA, 1024-bit, both SDKs), the master-query public key (RSA, 2048-bit, client SDK 4.3.8) and
the 32-byte phrase from which the legacy transform mask is built (both SDKs). They are fixed
vendor constants, not account secrets, and are reproduced with fingerprints in
[embedded-constants.md](cloud-auth/embedded-constants.md), together with the master host-name
suffixes. READ.

## End-to-end flow

```
App                     ZWO remote API          SDK (client)       Master / P2P servers      Device
 |  GET my-device[/detail]|                         |                     |                     |
 |----------------------->|                         |                     |                     |
 |  GET online-link       |                         |                     |                     |
 |----------------------->|                         |                     |                     |
 |<-- uid, licence, user/pass, conId                |                     |                     |
 |  POST device-log/report (p2pConnectStart, async) |                     |                     |
 |----------------------->|                         |                     |                     |
 |  set licence, init agent, connect(uid) --------->|                     |                     |
 |                        |                         |-- master query ---->|                     |
 |                        |                         |<- P2P server list --|                     |
 |                        |                         |-- precheck -------->|                     |
 |                        |                         |<- precheck reply ---|                     |
 |                        |                         |-- relay / punch --->|<-- registration ----|
 |                        |                         |<===== IOTC session ======================>|
 |                        |                         |-- tunnel auth (user/pass) ------------->|
 |<-- connected ------------------------------------|                     |                     |
 |  POST device-log/report (succeed/failed)         |                     |                     |
 |  ... use tunnel ...                              |                     |                     |
 |  POST device-p2p/stop {conId}                    |                     |                     |
```

READ for the app order (select device, `online-link`, record `conId` and report start, install
licence, initialize agent if needed, connect two tunnels, report the result). The device is
selected from the `my-device` list or detail record; a detail fetch immediately before
`online-link` is established only on the transport-loss recovery path (READ). The device side
installs its licence, resolves its master, queries the P2P server list, registers and then
refreshes registration in the background. READ. Detail and timers:
[state-timers.md](cloud-auth/state-timers.md).

R2. A client MUST obtain a fresh allocation with `online-link` for every new connection,
including recovery after transport loss. READ (app behaviour). Reuse of an old allocation:
unresolved (server-side); see [http-api.md R14](cloud-auth/http-api.md#allocation-online-link).

R3. Single-session enforcement is visible at cloud allocation (busy replies). No device-side cap
of one IOTC session was found. Separately, the device's handler for a repeated tunnel-server
start request refuses a request for the same UID with a different `srcId` while less than 70 s
(firmware 9.31) or 65 s (firmware 9.75, both builds) have elapsed or the old session is still
connected; this is not an allocation lifetime. READ
(absence of a cap; device check) / OBSERVED (2026-10-12, cloud busy replies). See
[http-api.md: Observed single-session enforcement](cloud-auth/http-api.md#observed-single-session-enforcement).

## Bundled firmware version comparison

Firmware 9.31 ships a 64-bit and a 32-bit imager. Both report SDK integer `0x04030603` (SDK
4.3.6, build 3). Their SDK version strings differ: the 64-bit build's is 48 characters (an
`..._openssl_Arm_RV1126BQ_13.3.0`-style build tag), the 32-bit build's is 43 characters (an
`..._openssl_Arm_rv1126_8.3.0`-style tag). The Android client reports `0x04030800` and a
37-character string ending `_openssl_android`. READ. The exact strings are build identifiers
returned by the SDK's version-string call; a stand-in device SHOULD send its own string rather
than copy one.

Firmware 9.75 (app 3.4.0) keeps the device SDK at version word `0x04030603` with the same revision
strings (48 and 43 characters) in both builds (READ), so there was no SDK upgrade. Differences are
confined to the build: the 9.75 SDK is built without its logging, so the source-path strings are
gone; many message handlers are inlined or folded, so the named out-of-line handler functions fall from 24
to 15 in the 64-bit imager. That is compiler inlining: the packet dispatcher handles the same opcode
set as in 9.31 and no master or relay wire message was added or removed (READ; details in
[iotc/index.md: Firmware 9.75 build comparison](../transport/iotc/index.md#firmware-975-build-comparison); the 32-bit split
differs again). The three
embedded public keys are unchanged ([embedded-constants.md](cloud-auth/embedded-constants.md)). The
licence source and the srcId gate changed ([sdk-licence.md R46a](cloud-auth/sdk-licence.md#device-side-sdk-start),
[http-api.md: `srcId` stability and the busy window](cloud-auth/http-api.md#srcid-stability-and-the-busy-window)).

The iOS app 3.4.0 network framework embeds SDK 4.3.6 build 3 (the Android 3.3.2 value above is
Android-specific, not evidence of an iOS change), reports login version `0x04030603`; the device accepts either client version, so the login
version is not a client gate (READ). iOS app 3.4.0 installs two tunnel mapping groups. One contains remote ports 4800, 4801, 4804, 4554, 4555, 4361 and 80; the other contains 4350 and 4700. Local ports match remote ports except remote 80 maps to local 40080. The client creates one connection per group and dispatches the connection attempts asynchronously. It signals success after all results are nonnegative, or failure on a negative result; its group wait has no time limit. READ for client configuration and control flow ([seestar-profile.md R72a](../transport/p2p-tunnel/seestar-profile.md#port-mapping-profile)). The examined main account headers, metadata and third-party signing builders are readable and are described in [boundaries item 9](account-login/boundaries.md). READ. Actual scheduling, complete cleanup, backend requirements and interoperability remain unresolved.

A targeted comparison of the 32-bit build against the 64-bit build (not a full packet-handler
comparison) found, READ:

| Function | 32-bit compared with 64-bit |
|---|---|
| Licence check | Same version-1 / Base64 / raw RSA / repeating XOR / SHA-256 with byte 0 set to `0x11` |
| Licence install | Same cleared state and JSON field handling |
| Master domain name | Same role, region, realm and standalone branches |
| Master resolution cache | Same reuse of a matching name for under 60 s |
| `0x1007` query | Same 54-byte message and offsets |
| `0x0120` register | Same header and first TDU; second TDU length 44, body 112, total 128 (version string plus NUL at bytes 84–127) |
| Tunnel server start | Same separate callback storage and plain device login |

R4. A stand-in device MUST size the `0x0120` second TDU from its own version string; the body
length is not fixed across builds. READ (two builds), INFERRED (rule).

## Open questions

- The opaque reply-field questions remain unresolved (server-side): `0x1008` bytes 36–51 and 68–69, legacy hello's first 16 reply-body bytes and remaining hello fields, legacy `0x0212`/`0x0215`/`0x0216` bytes 40–51, and the short `0x0229` form in [master-legacy.md](cloud-auth/master-legacy.md); `0x100c` bytes 18–19, 40–55 and 72–73, and precheck-record reply bytes 18–19, 48–59 and 70–71 in [master-record.md](cloud-auth/master-record.md). Android app 3.3.2 constructs a `0x0806` connection-result record with a four-byte record-session prefix and a 544-byte inner message containing a 528-byte body; see [relay.md](cloud-auth/relay.md#record-relay-messages-client-sdk). READ for local construction and copied sources. Complete meanings of copied opaque blocks, actual transmission and server interpretation remain unresolved. Firmware 9.31, firmware 9.75 and iOS app 3.4.0 telemetry parity is not established.
- Firmware 9.31 and 9.75, both imager builds: local conversion of a 16-byte address slot reads the port bytes at 2–3 and IPv4 bytes at 4–7. It formats those address bytes as numeric IPv4 text and passes that text to the platform resolver with unspecified family and datagram socket type. On successful resolution, an IPv4 result retains the original IPv4 bytes; the other branch copies sixteen bytes from the returned sockaddr's IPv6-address position. The input port bytes are preserved. The resulting local endpoint has a family tag at byte 0, port at bytes 2–3 and address at bytes 4–19; it is distinct from the wire slot. READ. Resolver failure behavior, deployed NAT64 synthesis and prefix, and server meanings of ignored address bytes and opaque punch metadata remain unresolved; see [iotc/index.md: Open questions](../transport/iotc/index.md#open-questions).
- How the cloud derives the licence and tunnel account it sends in `p2p_message` (R1a): see
  [sdk-licence.md R46a](cloud-auth/sdk-licence.md#device-side-sdk-start). Firmware 9.75: whether the
  cloud still sends `sdkLicenseKey`, what the embedded default licence is bound to, and the 32-bit
  parity of the licence change beyond string presence. unresolved (server-side) / unresolved.
- Firmware 9.75 device cloud link: specified in
  [device-cloud-link.md](cloud-auth/device-cloud-link.md) (MQTT parameters, duplicate-message
  filter, remote command types, P2P status report, monitor and occupy timers). Open questions there:
  the action string of command type 6, the success return value of the relay handler, whether the
  cloud accepts the status report's `code` member beyond `initFailed`, the host selection and
  fallback endpoints of the MQTT link (the broker address is a per-device input), and 32-bit logic
  parity (strings and symbols only). Server-side meaning of each reported status: unresolved
  (server-side).
- iOS 3.4.0: the endpoint mapping (`device-p2p/retrieve`, `device-p2p/stop`,
  `my-device/remote-unbind` with `deviceSn` and `deviceModel`), the response shapes and the
  remote-unbind error-code mapper are READ ([http-api.md: Optional remote-feature
  catalogue](cloud-auth/http-api.md#optional-remote-feature-catalogue)). iOS app 3.4.0: the confirmed device-details removal action invokes remote-unbind; the traced ordinary disconnect uses the stop operation after its status/identifier checks. A main caller of retrieve remains unresolved. The ticket parser accepts ticket, accessToken and expiresIn. Main Apple registration uses platform=apple and authType=email. The examined main third-party verification/registration builders use HMAC-MD5, while the separate bundled account-framework registration builder uses HMAC-SHA256. The installed tunnel profile has two mapping groups and signals success only after all connection results are nonnegative. The removal UI associates 400020 with a remotely connected device and 400021 with an offline device. READ for these client paths and messages. Server effects, the server meaning of 400002 and the other conditions, actual ticket responses/expiry, backend header/signature requirements and alternative framework entry paths remain unresolved. Android app 3.3.2 has the separate source paths described in the account-login and remote-operation chapters; parity remains unresolved.
- Server meaning of relay timeout 60000 versus 60: unresolved (server-side); see [relay.md
  R100](cloud-auth/relay.md#legacy-relay-messages-device-sdk).
- Server issuance, lifetime and revocation of allocations; cooldowns; meaning of unhandled cloud
  codes; whether the busy limit is per account, device or credential. unresolved (server-side).
- Live server-key rotation, DTLS parameters and TCP record coalescing: see [iotc/index.md: Open
  questions](../transport/iotc/index.md#open-questions). Live OpenSSL configuration: see [dtls.md
  R5](../transport/iotc/dtls.md#version-and-cipher-suite).
- Server handling of omitted optional members in the HTTP bodies. (App behaviour: request bodies use
  a default Gson without null serialization, so null members are omitted, and the one request enum
  is sent as `email`/`mobile`; see [http-api.md R10](cloud-auth/http-api.md). READ (app 3.3.2).)
  unresolved (server-side).
- The app library does not build Nebula gateway names from `nebulaDomainFromLicense`: the gateway
  builder is exported only by the global SDK library and has no caller in any app library, so the
  Seestar connection path never reaches it. Specified in [sdk-licence.md: Licence
  JSON](cloud-auth/sdk-licence.md#licence-json). READ (app library, SDK 4.3.8).
- Server meaning of relay result values outside the table, and of server alert codes other than 1
  and 2. unresolved (server-side).
- Reconnect retry limit and cooldown (app behaviour specified below). An automatic reconnect is one
  linear pass with no loop, backoff, counter or cooldown: local teardown, device detail, offline
  check, `online-link`, connect. Detail and `online-link` share a 30000 ms deadline, and a separate
  30000 ms watchdog ends the attempt with a timeout. Because a reconnect is admitted only from the
  connected state, a failed attempt cannot start another: each loss of an established session gets
  at most one automatic reconnect. A success re-arms it, and a failure leaves the link disconnected
  until the user connects again. The UI shows the failure and does not retry. A pending device
  reboot (a persisted flag, cleared by the next successful connect) suppresses it. Cancelling during
  a reconnect is checked between stages and ends the attempt as a cancelled connect. Manual connects
  count consecutive failures of certain TUTK and cloud codes, resetting the count at three, and
  impose no wait. What the count drives is not visible in the decompile. See [P2P tunnel
  R74–R75](../transport/p2p-tunnel/seestar-profile.md#readiness-and-reconnect). READ (app 3.3.2).
  Server-side rate limits remain unresolved (server-side).
- Whether any relay authorization path exists outside the P2P-server control exchange (for example
  an HTTP relay login). Not found; INFERRED absent, not proven.

## Appendix: How to validate on a live device (non-normative)

None of these steps was performed. INFERRED procedure.

1. Capture passively on a network and device you control while the official app connects and
   disconnects. Record timing, direction, DNS names, endpoints, lengths and record types only.
   Keep licences, tokens, passwords and auth keys out of any notes.
2. Compare master name construction, UDP port 10240, the TCP fallback ports, outer
   `51 cc 00 00` records and retry intervals with this chapter. Separate app and device traffic:
   their SDK versions differ.
3. With synthetic licences and packets, check byte order, zero gaps, lengths, the legacy
   transform, raw RSA block handling, P-256 secret truncation, GCM AAD and tag rejection. A
   self-roundtrip alone does not prove interoperability.
4. With authorized local instrumentation that does not persist secrets, correlate replies with
   UID, nonce and session transitions to confirm reply offsets and key/IV lifetimes.
5. Test a clean client on your own device and account: normal connect, stop, cancel, offline
   device, second session. Observe the official app first. Do not provoke repeated busy replies
   to guess a rate limit.
6. Test TCP fallback by blocking UDP locally; confirm cleanup after the 30 s app deadline.
