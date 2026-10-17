# Seestar protocol specification: overview

This is the entry chapter. It describes the whole stack, from UDP and TCP up to the JSON control
methods, names the device processes and their ports, and points to every other chapter. Nothing
sits above it. Below it are the layer chapters: [transport](transport/), [auth](auth/),
[control](control/), [guider](guider/), [media](media/) and [updater](updater/), plus the
machine-readable [catalog](../catalog/) and the generated method and event cards in
[docs](../docs/).

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients. Statements about what "the device" or "the app" does are descriptions.

Every claim carries one label (`CONVENTIONS.md`):

- **READ**: established by static analysis of firmware 9.31 or app 3.3.2.
- **OBSERVED(date)**: seen on a real device or in a real capture on that date. The live build was
  not matched to 9.31.
- **INFERRED**: a reasoned conclusion that neither source states directly.
- **unresolved**: not established. Listed in the open-question register ([Open-question register](#open-question-register)).
  **unresolved (server-side)** marks a question only the vendor's servers can answer (their
  validation, policy or meaning of a field the client does not read). The client behaviour around
  it is fully specified, so it is not a gap in what a client must do.

Basis: static analysis of Seestar firmware 9.31 (64-bit build as reference, 32-bit build as
corroboration), the Android app 3.3.2 and its native libraries, and wire observations of the
iOS app and a device. Examples use documentation addresses (192.0.2.x, 198.51.100.x,
203.0.113.x) and synthetic values.

## What the specification covers

- How a client reaches a Seestar: on the local network directly, or remotely through the ZWO
  cloud and the Kalay/IOTC peer-to-peer service.
- The remote transport: IOTC session, DTLS, the RDT reliable stream, and the P2P tunnel that
  forwards device TCP ports.
- Account and cloud authorization needed to open a remote session.
- The JSON control protocol on TCP 4700: framing, envelopes, verification, errors, events and
  the method set.
- The guider, image/file sockets, video, the serial bridge and the updater, including
  [package processing and manifests](updater/ota-package-handling.md) and
  [package contents](updater/firmware-975-package.md).
- The documented [BLE activation exchange and transport boundary](transport/ble.md).

Not covered: the app's user interface, astronomy algorithms inside the device, and other ZWO products.

## Protocol stack

### Remote path (through the cloud)

```text
  Client application                                   Cloud, beside the stack
 +-----------------------------------------------+    +------------------------------+
 | JSON control (4700), guider (4400), image and |    | ZWO account API (HTTPS)      |
 | file sockets (4800/4801/4804), video (4554/   |    |  login -> account token      |
 | 4555), HTTP (80), updater (4350/4361)         |    |  online-link -> SDK licence, |
 +-----------------------------------------------+    |   device UID, tunnel user/   |
 | local TCP listeners, one per mapped port      |    |   password, cloud conId      |
 +-----------------------------------------------+    +---------------+--------------+
 | P2P tunnel: 4-byte frames, channels = TCP     |                    |
 |  connections, login with tunnel credentials   |<-------------------+ credentials
 +-----------------------------------------------+                    |
 | RDT: reliable ordered byte stream, 20-byte hdr|                    |
 +-----------------------------------------------+                    |
 | DTLS 1.2 PSK (identity = tunnel username)     |<-------------------+ PSK source
 +-----------------------------------------------+                    |
 | IOTC session: 16-byte header (+12 ext),       |<-------------------+ licence, UID
 |  masked first 64 bytes, channel 0            |
 +-----------------------------------------------+    Kalay master and P2P servers:
 | UDP (master 10240, P2P, LAN search 32761)     |<-- rendezvous, NAT punch or relay
 | TCP fallback to master servers                |
 +-----------------------------------------------+
```

- The account API returns, per device, an SDK licence key, the device UID, a tunnel username and
  password, and a cloud connection id. READ. Their roles are in [Identifiers and secrets (roles only)](#identifiers-and-secrets-roles-only).
- The client asks Kalay master servers where the device is, then reaches it directly
  (hole-punched UDP) or through a Kalay relay. On the same LAN, Kalay's own LAN search on UDP
  32761 can find it. READ. See [IOTC](transport/iotc/index.md).
- DTLS 1.2 with a pre-shared key protects the session. READ; the negotiated suite was not
  observed. See [DTLS](transport/iotc/dtls.md).
- RDT turns IOTC packets into a reliable byte stream. READ. See [RDT](transport/rdt.md).
- The P2P tunnel multiplexes TCP connections over RDT. The Seestar profile maps nine device
  ports, in a primary group (4700, 4350) and a secondary group (80 via local 8080, 4554, 4555,
  4801, 4800, 4804, 4361). READ. See [P2P tunnel](transport/p2p-tunnel.md).
- On the device, the tunnel daemon connects to the application servers over loopback, so the
  device treats tunnelled clients as local. OBSERVED 2026-10-12. This affects verification
  ([session handshake](control/session-handshake/verification-and-roles.md#client-verification)).
- After the authenticated session is up, the app may move application bytes to a direct LAN TCP
  path that bypasses DTLS. READ; runtime use unresolved (Q29).

### Direct LAN path

```text
  Client                                  Device on the same network
    |-- UDP broadcast "scan_iscope" (4720) -->|   discovery, CRLF-framed JSON
    |<-- reply with model/name/state ---------|
    |== TCP 4700 (plaintext JSON lines) =====>|   control; verify_client required (firmware 9.31; config-dependent on 64-bit 9.75)
    |== TCP 4800/4801/4804, 4554/4555, ... ==>|   media, files, video
```

No IOTC, DTLS, RDT or tunnel is involved, and there is no transport encryption. READ. See
[LAN discovery](transport/lan-discovery.md) and [ports](transport/ports.md).

## Identifiers and secrets (roles only)

This specification never contains a value for any of these.

| Item | Obtained from | Role | Label |
|---|---|---|---|
| Account token | Account login | Authorizes account API calls. | READ |
| SDK licence key | `online-link` | Authorizes the Kalay SDK, selects master servers and supplies the packet mask for legacy framing. | READ |
| Device UID | `online-link` | Rendezvous target in the Kalay network. | READ |
| Tunnel username and password | `online-link` | P2P tunnel login; the username is the DTLS PSK identity and a hash of the password is the PSK. | READ |
| Cloud connection id | `online-link` | Names one remote allocation for report and stop calls. Not a packet channel. | READ |
| Verification key pair | Built into the app (private) and firmware (public) | Signs and checks the 4700 challenge. | READ |
| Client UUID and name | Chosen by the client | Guest/master identity on the control server. | READ |

See [account login](auth/account-login.md) and [cloud auth](auth/cloud-auth.md).

## Device processes and services

| Process | Port | Service | Label |
|---|---|---|---|
| Main imager (the imager, telephoto) | TCP 4700 | JSON control and events | READ |
| | TCP 4701 | Same method table as 4700; verification required, no guest checks, greeting or close effects | READ |
| | TCP 4800, 4804 | Image streams (binary header + payload) | READ |
| | TCP 4801 | Album and file transfer | READ |
| | UDP 4720 | LAN discovery (`scan_iscope`) | READ |
| Auxiliary imager (wide camera) | TCP 4702 | Its JSON control/events; events forwarded to 4700 | READ |
| | TCP 4804 | Wide image stream | READ |
| Guider (the guider) | TCP 4400 | Mount, guiding and system-time methods; events | READ |
| | TCP 4500 | Guide-camera images (binary frames) | READ |
| Serial bridge (in the guider) | TCP 4030 | Raw serial bridge; accepts a client only while its IP is verified on 4040 | READ |
| | TCP 4040 | Serial-bridge control server (`set_settings`, `disconnect`) | READ |
| Updater (the updater) | TCP 4350 | JSON control and progress events | READ |
| | TCP 4361 | Binary firmware upload | READ |
| HTTP file server | TCP 80 | Downloads from the image store; uploads; no authorization | READ |
| Imager / auxiliary imager | TCP 4554 / 4555 | RTSP video while streaming | READ |

The imager forwards control methods it does not know to the guider, so a 4700 client reaches
guider methods without opening 4400. READ. See
[session handshake](control/session-handshake.md#relay-of-unknown-methods-to-the-guider).

Method counts: the main imager table registers 269 names (264 in the 32-bit build), the guest
table 5, the guider 105 in its main table. READ.

## A typical session

1. LAN: discover the device on UDP 4720, or remote: log in, call `online-link`, open the IOTC
   session, DTLS, RDT and the tunnel, then connect to the local listener for 4700.
2. Open TCP 4700, receive the [`Version`](../docs/control/events/Version.md) greeting, call `get_verify_str` and `verify_client`.
3. Initialize: set language, time and location, set the client name and UUID, read device state.
4. Send commands; read replies (matched by `id`) and events (`Event` member) from one stream.
5. Send `test_connection` at least every 15 s. Open image, file or video sockets as needed.

Details: [session handshake](control/session-handshake.md), [errors](control/errors.md),
[events overview](control/events-overview.md).

## Reading guide

| Directory | Contents |
|---|---|
| [transport/](transport/index.md) | [Ports](transport/ports.md), [LAN discovery](transport/lan-discovery.md), [IOTC session](transport/kalay-iotc-session.md) and [IOTC detail](transport/iotc/index.md), [RDT](transport/rdt.md), [P2P tunnel](transport/p2p-tunnel.md). Firmware 9.75 notes: [listener set](transport/ports.md#device-ports), [IOTC build comparison](transport/iotc/index.md#firmware-975-build-comparison), [tunnel profile](transport/p2p-tunnel/seestar-profile.md#integration). |
| [auth/](auth/index.md) | [Account login](auth/account-login.md) and [cloud authorization](auth/cloud-auth.md): licence, master servers, relay allocation; the firmware 9.75 licence change is in [SDK licence R46a](auth/cloud-auth/sdk-licence.md#device-side-sdk-start). |
| [control/](control/index.md) | The 4700 protocol: [session handshake](control/session-handshake.md), [errors](control/errors.md), [events](control/events-overview.md), and one chapter per feature area (viewing, stacking, plans, [mosaic](control/mosaic.md), mount, focus, network, time and location, settings, calibration, polar alignment, object lists, special modes, [function states](control/function-states.md), [secure communication](control/secure-communication.md)). |
| [guider/](guider/index.md) | Guider server on 4400, guide images on 4500, the serial bridge on 4030. |
| [media/](media/index.md) | Image sockets 4800/4804, file and album socket 4801, RTSP and HTTP video, SMB file sharing. |
| [updater/](updater/index.md) | [Updater control on 4350 and firmware upload on 4361](updater/index.md) (its [open questions](updater/index.md#open-questions)), the [firmware 9.75 changes](updater/firmware-975-changes.md) and the [firmware 9.75 package contents](updater/firmware-975-package.md). |
| [catalog/](../catalog/) | Machine-readable YAML for every service, method, event and schema, with a label on every field. |
| [docs/](../docs/index.md) | Cards generated from the catalog, indexed by service: `docs/<service>/methods/<name>.md` and `docs/<service>/events/<Name>.md`. |

Start with this chapter, then [session handshake](control/session-handshake.md) for a LAN client,
or [transport](transport/index.md) and [auth](auth/index.md) first for a remote client.

## Glossary

| Term | Meaning |
|---|---|
| Alert | Event sent before the device closes a connection over the client limit (code 429). |
| App | The official Seestar mobile app (Android 3.3.2 unless stated). |
| Batch | A JSON array of requests on one line. |
| conId | Cloud connection id from `online-link`. |
| DTLS | Datagram TLS 1.2, used with a pre-shared key inside the IOTC session. |
| Event | An unsolicited JSON line with an `Event` member and no `id`. |
| External / internal connection | Internal: source address equals the device's own `localhost` address; everything else is external. |
| Guest mode | Device setting that allows up to 8 client IPs and limits non-master clients to five methods. |
| Guider | Device process for mount control and guiding (TCP 4400). |
| Imager | Main device process for cameras, stacking and plans (TCP 4700). |
| IOTC | The Kalay (ThroughTek) session layer over UDP, with master servers and relays. |
| Kalay | The vendor peer-to-peer platform used for remote access. |
| Licence key | SDK licence string from the account API; authorizes the SDK and masks packets. |
| Master | The guest-mode client with full method access. |
| Master server | Kalay server that tracks where a device UID is reachable. |
| P2P tunnel | Kalay module that forwards TCP connections over RDT in 4-byte-header frames. |
| PSK | Pre-shared key for DTLS, derived from the tunnel password. |
| RDT | Kalay reliable data transport: ordered byte stream over IOTC. |
| Relay (guider) | Imager forwarding of unknown 4700 methods to 4400. |
| Relay (Kalay) | Kalay server forwarding packets when direct UDP fails. |
| UID | The device's Kalay identifier. |
| Verification | The `get_verify_str` / `verify_client` signature check on control ports. |
| `err_code` | The firmware's thread-local error variable that handlers forward into replies. |

## Open-question register

Spec-level questions. "Static" means more firmware or app analysis could settle it; "capture"
means it needs device observation.

| ID | Question | Settle by |
|---|---|---|
| Q01 | Licence realm and the set of account and master endpoints per region. Service selection is settled: the app uses `c-master` only ([master-legacy: Master host names](auth/cloud-auth/master-legacy.md#master-host-names)). | both |
| Q02 | Socket-address encoding for IPv6 and unusual address families. | static |
| Q03 | Meaning of metadata in the 030d IOTC message. | both |
| Q04 | Trailing fields in legacy 0301 messages. | static |
| Q05 | Purpose and content of telemetry messages 0804 and 0806. | both |
| Q06 | ECC key rotation and GCM IV reuse policy in the modern envelope. | static |
| Q07 | TCP segmentation of the modern envelope on the TCP fallback. | capture |
| Q08 | SDK defaults and the scheduling of retries and probes. | static |
| Q09 | NAT-type values and how they steer the connect path. | both |
| Q10 | Complete validation rules and HMAC modes on received packets. | static |
| Q11 | Equivalence of the 32-bit and alternate builds. | static |
| Q12 | How the cloud derives the licence and tunnel credentials it sends to the device (no IOTC auth key is set on Seestar). | server |
| Q13 | Account token lifetime and refresh (server-side). | capture |
| Q14 | Cloud cooldowns and error semantics (server-side). | capture |
| Q15 | Enumerations and time units in HTTP API fields (server-side for response values and units). | both |
| Q16 | Reconnect races between cloud, IOTC and tunnel layers. | both |
| Q17 | Device sleep and wake lifecycle for remote sessions. | capture |
| Q18 | Effect of OpenSSL configuration on DTLS. | static |
| Q19 | DTLS version and cipher suite actually negotiated. | capture |
| Q20 | DTLS flight retransmission and loss handling. | capture |
| Q21 | RDT FIN latency. | capture |
| Q22 | RDT sequence-number wrap. | static |
| Q23 | RDT window tuning and buffer overflow. | both |
| Q24 | ACK and shutdown races in RDT. | both |
| Q25 | Parser limits for malformed input at each layer. | static |
| Q26 | Fragmentation of the tunnel login (1000 versus 1004 bytes). | capture |
| Q27 | Tunnel SETUP rejection quirk and channel reuse. | both |
| Q28 | Timing of tunnel PAUSE and resume. | capture |
| Q29 | Whether and when the LAN-direct bypass is used, including on iOS. | capture |
| Q30 | End-to-end interoperability of an independent client. | capture |
| Q31 | Unverified same-LAN 4700 behaviour (READ says silent consumption). | capture |
| Q32 | Order of replies against the events they cause. | capture |
| Q33 | Large numbers, Unicode and duplicate keys in requests. | both |
| Q34 | Factory verification mode. | static |
| Q37 | Whether the MAC-based master restore can pick the wrong connection behind a proxy (connections are per socket and master follows `cli_uuid`, READ). | both |
| Q38 | Relay behaviour inside batches (relay timeout or connection failure gives 103, READ). | both |
| Q40 | Whether buffer, batch-stacker and star-trail stacker results can be values outside the code table (camera SDK codes are mapped; mount codes and 9004/9005 pass through, READ). | static |
| Q41 | iOS behaviour beyond the observed connect order. | capture |
| Q43 | Why the keyed `client` section of `get_device_state` was empty on a tunnel session. | capture |
| Q44 | Idle close on a verified LAN connection (15 s READ; only tunnel-internal connections observed). | capture |

### Chapter open questions

- [Second-camera relay routing](control/session-handshake/relay-routing.md#open-questions)

- [BLE transport](transport/ble.md#open-questions)

Each chapter lists its own narrower open questions. `tools/lint.py` checks that every such
section is listed here.

- [Account login and token lifecycle](auth/account-login/boundaries.md#open-questions)
- [Cloud authentication and relay authorization](auth/cloud-auth.md#open-questions)
- [Calibration frames](control/calibration-frames/frames-and-interactions.md#not-covered-or-unresolved)
- [Device state and settings](control/device-state-and-settings.md#open-questions)
- [Control errors: codes, wire shapes and irregular replies](control/errors.md#open-questions)
- [Events overview](control/events-overview.md#open-questions)
- [Focus and filter wheel](control/focus-and-filter.md#not-covered-or-unresolved)
- [Legacy plans, sequences and plan observation](control/legacy-plans-and-sequences/events-and-observation.md#open-questions)
- [Maintenance, activation and diagnostic methods](control/maintenance.md#open-questions)
- [Miscellaneous control methods](control/misc.md#open-questions)
- [Mosaic capture](control/mosaic.md#open-questions)
- [Mount and motion](control/mount-and-motion.md#open-questions)
- [Network configuration](control/network.md#open-questions)
- [Object lists, sky objects and target names](control/object-lists.md#open-questions)
- [Plan scheduling (ViewPlan)](control/plan-scheduling.md#not-covered-or-unresolved)
- [Polar alignment and mount sensors](control/polar-alignment.md#open-questions)
- [Power and storage](control/power-and-storage.md#open-questions)
- [Control session: heartbeats, initialization, ordering and secondary servers](control/session-handshake/liveness-and-ordering.md#open-questions)
- [Solving, goto and annotation](control/solving-and-annotation.md#not-covered-or-unresolved)
- [Function states: settings reset, motion monitor, smart follow, sky replay](control/function-states.md#open-questions)
- [Special modes: Sun, Moon and planets, tracking, recording, streaming, functions](control/special-modes.md#open-questions)
- [Stacking](control/stacking.md#not-covered-or-unresolved)
- [Time and location](control/time-and-location.md#open-questions)
- [Viewing and exposure](control/viewing-and-exposure.md#not-covered-or-unresolved)
- [Guider process](guider/index.md#open-questions)
- [Mount serial command set](guider/mount-serial-commands.md#open-questions)
- [Serial bridge (ser2net)](guider/serial-bridge.md#open-questions)
- [Album and file socket 4801](media/files-and-album.md#open-questions)
- [Image sockets 4800 and 4804](media/image-sockets.md#open-questions)
- [Media channels](media/index.md#open-questions)
- [SMB file sharing](media/smb.md#open-questions)
- [Video: RTSP, RTMP pipeline and AVI recording](media/video.md#open-questions)
- [Kalay/IOTC session](transport/iotc/index.md#open-questions)
- [LAN discovery and device selection](transport/lan-discovery.md#open-questions)
- [P2P tunnel (TCP port forwarding)](transport/p2p-tunnel/index.md#open-questions)
- [Port map](transport/ports.md#open-questions)
- [RDT reliable data channel](transport/rdt.md#open-questions)
- [Updater process](updater/index.md#open-questions)
- [Firmware package contents: 9.31 to 9.75](updater/firmware-975-package.md#open-questions)
- [Secure communication](control/secure-communication.md#open-questions)

