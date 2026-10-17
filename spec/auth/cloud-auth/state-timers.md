# Cloud auth: state, retries, timers and teardown

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file collects the
app workflow states, the SDK state transitions tied to authorization replies, the timers, the
mapping of stored conditions to SDK API errors, and teardown and recovery. Message layouts are in
[master-legacy.md](master-legacy.md), [master-record.md](master-record.md) and
[relay.md](relay.md). Transport-level selection and fallback timing belong to
[Kalay/IOTC session](../../transport/iotc/index.md); tunnel mapping and readiness to
[P2P tunnel](../../transport/p2p-tunnel/index.md).

Basis: static analysis of app 3.3.2 and firmware 9.31; firmware 9.75 differences are tagged. Numeric states are internal SDK values,
not wire fields.

## App workflow

Input: a valid stored ZWO token ([account login](../account-login.md)). READ.

| State | Event | Action | Next |
|---|---|---|---|
| idle | user connects (device selected from the list or detail record) | `GET online-link` | allocating |
| allocating | `online-link` success | record `conId`; report `p2pConnectStart` (async) | connecting |
| allocating | cloud error | map code ([http-api.md: Cloud and workflow error codes](http-api.md#cloud-and-workflow-error-codes)) | idle |
| connecting | — | install licence; init agent if first; connect primary and secondary tunnels | connecting |
| connecting | both tunnels up | report `p2pConnectSucceed` | connected |
| connecting | -30002 | wait 250 ms, retry once if attempt still current | connecting |
| connecting | error / 30 000 ms deadline | clean up; report failure or timeout-cancel | idle |
| connecting | user cancel or newer attempt | discard result (it never becomes the current session) | idle |
| connected | user disconnect | stop (if `conId` known), close channels, native disconnect, clear state | idle |
| connected | transport lost | local disconnect **without** stop; fetch detail; new `online-link`; connect | connecting |

READ, except that report names on the failure rows are INFERRED from the declared event set.

R120. A cancelled or superseded attempt MUST NOT become the current session. READ (app behaviour,
obligation INFERRED).

R121. Recovery after transport loss MUST request a new allocation. READ (app behaviour). The app
also has a readiness timeout of 30 000 ms (disconnect, local -10087) and a guarded reconnect path
for -30006; see [P2P tunnel](../../transport/p2p-tunnel/seestar-profile.md#readiness-and-reconnect). READ.

R122. Teardown: when stop is requested and a nonblank current `conId` exists, send
`POST /v1/device-p2p/stop`; log and ignore its failure; clear current and pending IDs; disconnect
natively; clear remote info; publish "disconnected". READ.

## Device registration flow

Install licence → initialize device SDK → resolve device master → query group / P2P server list
→ register with P2P servers → refresh registration and keepalive in the background. READ. DNS
failure logs -2. READ.

## SDK transitions on authorization replies

READ. Not a complete enumeration of the transport state machines.

| Event | Transition / action |
|---|---|
| Matching master list reply | Device UDP query 1 → 2; client record query UDP 1 → 2 or TCP 4 → 5 |
| Matching precheck reply | Device UDP 5 → 6; device TCP overall 10 → 11 and matched server entry 10 → 13; client record UDP 5 → 6 or TCP 11 → 12 |
| Relay result -7 | Request kept pending; device UDP relay 1 → 2 where applicable |
| Relay result 0 | Advance relay status; if already connected, request session info again |
| Device TCP relay request timeout | 13 → 15 when elapsed > 59 999 ms |
| Device TCP relay follow-up | 16/17 request session info; 19 removes the task as success; 15/18 remove it as failure |
| Unlicensed, auth or port refusal | Flags stored; the connect loop returns a mapped error ([API error mapping](#api-error-mapping)) |

## API error mapping

The client SDK maps stored conditions to connect errors (READ):

| Condition | Error |
|---|---:|
| SDK not initialized | -12 |
| Search stopped | -27 |
| Unlicensed (`0x0008`) | -10 |
| Advanced service unsupported | -40 |
| Device refused (relay -1) | -48 |
| No relay (relay -5) | -43 |
| Device asleep | -64 |
| Port rejected (relay -9) | -67 |
| Wrong auth key (relay -22) | -68 |
| Device authentication disabled | -69 |
| Device not listening | -24 (a counter-dependent path gives -48) |

These API errors are distinct from relay results and cloud codes. READ.

## Timers

Call-site values. They are task intervals and lifetimes, not guaranteed packet spacing. READ.

| Activity | Value |
|---|---|
| App remote attempt | 30 000 ms overall |
| App port-busy retry | one retry after 250 ms on -30002 |
| SDK session-alive timeout | 30 s (app and device) |
| Synchronous master query | 50 waits of 100 ms (about 5 s); UDP sent every fifth wait (500 ms), cycling up to three masters; TCP paths queried separately |
| UDP device-query task | immediate send, then every 500 ms for up to 60 000 ms |
| UDP relay request and session-info tasks | immediate, then 500 ms / 60 000 ms |
| Device TCP relay request | resend at ≥ 2000 ms elapsed; give up after > 59 999 ms |
| Device initial P2P login | poll 100 ms; send interval 500 ms doubling to 10 000 ms; deadline 60 s |
| Device login interval override | environment `IOTC_INIT_LOGIN_INTERVAL_MS`, clamped 100–10 000 |
| Client background registration | 40 000 ms |
| Client background NAT check | 10 000 ms |
| Client UDP-login retry while on fallback | 3600 s; environment `IOTC_DEVICE_RETRY_UDP_LOGIN_INTERVAL_SEC`, clamped 1–3600 |
| Client background master resolution | 86 400 000 ms (24 h; a nearby log text says 12 hours) |
| Client group-list refresh | random 32 400–54 000 s; environment `IOTC_UPDATE_SERVER_INTERVAL_SEC` (non-negative) clamped 60–43 200 |
| Device forced group refresh | query task 20 000 / 86 400 000 ms; re-registration task 1000 / 6000 ms |

Firmware 9.75 (READ): the device-side different-`srcId` busy gate is 65 s instead of 70 s
([http-api.md: `srcId` stability and the busy window](http-api.md#srcid-stability-and-the-busy-window)). The 9.75 device's P2P
monitor and occupy timers (READ): the monitor ticks every 300 s instead of 60 s, stops P2P after 12 idle
ticks (60 min; 9.31: 30 ticks of 60 s, 30 min) and exits after more than 24 ticks (about 125 min; 9.31: more
than 60 ticks); the occupy timeout thread sleeps 65 s instead of 70 s
([device-cloud-link.md R46m and R46n](device-cloud-link.md#p2p-monitor-and-occupy-timers)). The SDK timers above
(retry and registration intervals) are unchanged in the call sequences compared; the 10 000 ms and 60 000 ms
constants seen in the 9.75 LAN search handler are the 9.31 session recycler's, inlined, not new timers
([iotc/index.md: Firmware 9.75 build comparison](../../transport/iotc/index.md#firmware-975-build-comparison)).

The random-range helper returns `low + lrand48() mod (high - low + 1)`. READ. Nothing establishes
a uniform or collision-free nonce from it. INFERRED.

Further transport timers (10 ms poll, 20 ms TCP workers, 1500/5000 ms gates, background task
300 000 ± up to 120 000 ms, recent-RID expiry ≥ 20 000 ms, creating-session recycler 10 000 /
60 000 ms, NAT refresh ≥ 25 000 ms) are specified in
[Kalay/IOTC session](../../transport/iotc/connect.md) and [IOTC session](../../transport/iotc/session.md#timers). READ.

R123. No fixed retry limit or service cooldown is established at this layer. A client SHOULD
follow the observed busy-window guidance in
[http-api.md: Observed single-session enforcement](http-api.md#observed-single-session-enforcement). OBSERVED (window);
limits unresolved (server-side).

## Failure handling

- Device login task creation failure: delete created tasks, close device TCP server connections,
  clear active login state, return -61. READ.
- Licence or crypto parse failure returns before usable state is installed. READ.
- The inspected handlers reject failed GCM tags and the listed source, UID, nonce and session
  mismatches. They do not establish universal rejection of malformed packets; type 14 lacks a
  length guard ([relay.md: Server alerts](relay.md#server-alerts)). READ.

R124. An implementation MUST bound every attempt with its own deadline and clean up on expiry,
independent of SDK-level validation. INFERRED (the app does so, READ).
