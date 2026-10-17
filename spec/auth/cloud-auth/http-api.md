# Cloud auth: ZWO HTTP authorization and session allocation

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file covers the
ZWO remote API: common headers and envelope, device selection, remote-session allocation
(`online-link`), reports, stop, cloud error codes and the optional remote-feature calls. The
token used here comes from [account login](../account-login.md); the allocation it returns is
consumed by the SDK ([sdk-licence.md](sdk-licence.md)).

Basis: static analysis of app 3.3.2 (Java layer); observations from 2026-10-10 to 2026-10-12.

## Host, transport and headers

The remote API is a JSON-over-HTTPS service on "the ZWO remote API host",
`https://api-ithings.zwoastro.com` in production
([embedded-constants.md: ZWO vendor HTTP API hosts (app)](embedded-constants.md#zwo-vendor-http-api-hosts-app)). Release
builds use the production host; development builds use a separate test host,
`http://api-ithings-test.zwoastro.cn`. Both come from a JSON asset in the app. READ. Paths below
are relative to the host root; the app joins them with exactly one `/`. READ.

R10. Bodies are JSON objects serialized with default Gson naming (Java member name = JSON
member name). READ. The remote-API client uses a plain, default-configured Gson instance for
request bodies (a scalar converter registered ahead of it handles only string and primitive bodies): null members are
omitted rather than written as `null`, no request member is renamed, and HTML-sensitive
characters in strings are written as `\u` escapes. A null query parameter is left out of the
URL. READ (app 3.3.2). The only enum in a request body is the transfer-code `type`, sent as the
string `email` or `mobile`. READ (app 3.3.2).

Every request carries these headers (READ):

| Header | Value |
|---|---|
| `Authorization` | The stored ZWO token, verbatim, with **no** `Bearer ` prefix. Omitted if the token is empty or the request is marked "no authentication". |
| `X-Lang` | Locale language tag with the script removed; `zh` and `zh-Hans` become `zh-CN`; any `en-*` becomes `en`. |
| `x-service-platform` | Platform name; `seestar` for this app. |
| `country_code` | Locale country. |
| `x-params` | JSON object text, see below. |

`x-params` is the text of a JSON object whose members are all strings: `channel` (`google` for
the Google release), `platform` (always `android` from this app), `model` (phone model),
`country_code`, `os_version` (Android API level as a string) and `app_version` (`3.3.2`). READ.
Synthetic example:

```text
x-params: {"channel":"google","platform":"android","model":"Phone1","country_code":"US","os_version":"34","app_version":"3.3.2"}
```

R11. A client MUST send the token as the raw `Authorization` value. It SHOULD send the other
headers with the same meaning; whether the server requires them is unresolved (server-side).

R12. App timeouts are 70 s connect, 60 s write, 120 s read, with retry on connection failure.
The remote-connect workflow additionally bounds one attempt at 30 000 ms. READ.

## Response envelope

Every reply body is a JSON object `{ "code": int, "data": <typed>, "msg": string }`. READ.

| HTTP result | App interpretation (READ) |
|---|---|
| 2xx with a non-null body | Success; `code` is passed up but **not** checked here |
| 2xx with an empty body | Unknown error |
| 400 with a body | Envelope parsed; `code`/`msg` reported as the error |
| 401 | Token expired (see [account login](../account-login/lifecycle.md#token-renewal-expiry-and-logout)) |
| Other | HTTP status and reason reported |
| Network exception | Network error; unknown host is reported separately |

R13. A client MUST treat HTTP 401 as token expiry and MUST read `code` from a 400 body to
classify cloud refusals. OBSERVED (2026-10-12): success envelopes carried `code` 200.

Presence and null handling (READ unless marked). Replies are decoded by a plain Gson converter:
unknown members are ignored; an absent member, or `null` on an int member, reads as 0; `null` on
a string or object member reads as null. The app's Kotlin reply classes are built without their
constructors, so members declared non-null can still be null. INFERRED (standard Gson
behaviour). Gson is bundled beside kotlinx.serialization and Moshi. READ (presence). The bundled Gson is
version 2.13.1 (the library's own build-config version constant). READ (app 3.3.2).

| Envelope member | 2xx reply | 400 reply |
|---|---|---|
| `code` | Not compared anywhere found; absent or null tolerated | Read; absent or null reads as 0 |
| `msg` | Not required | **Required**: a missing or null `msg` fails a not-null check inside the HTTP callback |
| `data` | Per call ([Device selection](#device-selection), [Allocation: `online-link`](#allocation-online-link)) | Not read |
| whole body | Empty or literal `null`: unknown error | Literal `null`: the app fails reading `code` |

No envelope `code` value marks success on the remote API; the app decides on HTTP status alone.
OBSERVED (2026-10-12): success replies were HTTP 200 with `code` 200 and a string `msg`; refusals
were HTTP 400 with a cloud code ([Cloud and workflow error codes](#cloud-and-workflow-error-codes)).

R13a. A server MUST send a string `msg` and an integer `code` on every 400 reply. A client SHOULD
decide success on HTTP status and SHOULD NOT require `code` 200 in a 2xx body. INFERRED.

## Device selection

| Call | Parameters | `data` |
|---|---|---|
| `GET /v1/my-device` | query `current`, `pageSize`, `isContainShared` (nullable integers) | page of device records |
| `GET /v1/my-device/detail` | query `deviceSn`, `deviceModel`, `onlyQueryOwner` (nullable boolean) | one device record |

READ. The page wrapper declares `type`, `id` (strings), `attributes`/`data` (one record),
`items` (list), `list`, `current` (nullable int), `total`, `unReadCount` (ints). READ. These are
the app's accepted shapes; which members a server fills is unresolved (server-side).

Page handling (READ, app 3.3.2 device-list screen, page size 20): a null or absent `items` is
treated as an empty page. Page 1 replaces the accumulated list; later pages are appended as
received, without removing duplicates or keying by serial. After each page the screen stores
the reply's `current` as the current page when it is present and positive (otherwise the
requested page) and stores `total`. Before loading another page it checks `total` > number of
accumulated items; if not, it ends paging without a request. A further page is requested only
from the list's load-more trigger, as `current` + 1. So the app never requests a page past the
last when `total` is right; an absent or null `total` (read as 0) ends paging after page 1, and a
low `total` hides devices. INFERRED from the READ check. A failed page leaves the accumulated
list and allows a retry. Server behaviour for a page past the last is unresolved (server-side).
OBSERVED (2026-10-12): `current`, `pageSize` and `total` were integers and `items` an array; page
counts were not recorded.

Each entry is a separate selectable record, and the chosen record supplies the `deviceSn` and
`deviceModel` sent to detail and reboot. READ. Precheck before allocation (READ, app 3.3.2,
complete trace of the connect workflow): the app requests detail with the chosen pair and
`onlyQueryOwner=false`. A non-2xx or failed detail reply ends the attempt with that error. On a
2xx reply the only test is the offline test on `deviceStatus` ([Device selection](#device-selection) below). Otherwise the detail
reply's record replaces the chosen one: its `deviceSn` and `deviceModel` are sent to
`online-link` and later in the connection reports. The detail reply's serial
and model are never compared with the request, and its `data` is not null-checked; a null
`data` ends the attempt with an app exception (INFERRED). The same precheck runs before the
app's automatic reconnect after transport loss.

R13c. A client SHOULD identify a device by the (`deviceSn`, `deviceModel`) pair. Exact duplicate
pairs: use the first and log the duplicate. Same serial, different models: keep them distinct,
and refuse a serial-only selection as ambiguous. A client SHOULD refuse to allocate when the
detail reply's `deviceSn` or `deviceModel` differs from the request. INFERRED (policy).

R13d. A client SHOULD treat the catalogue as complete when the accumulated item count reaches
`total`, and MUST NOT treat a page as complete evidence when `total` is absent, null, or below
the count already received. A client SHOULD apply R13c only to a catalogue complete in this sense,
and SHOULD refuse a serial-only selection when it is not. A client MAY request one page past
`total` as a cross-check, but MUST NOT require any particular reply to it (empty `items`, null, a repeated page or an error), since
none is established. INFERRED (policy).

Device record members (READ, as declared by the app):

| Type | Members |
|---|---|
| string | `address`, `deviceSn`, `ssid`, `deviceModel`, `subModel`, `userId`, `timezone`, `shareExpirationTime`, `shareStartTime`, `transferStatus`, `deviceAlias` |
| int | `createTime`, `deviceId`, `id`, `updateTime`, `deviceStatus`, `shareStatus` |
| double | `latitude`, `longitude` |
| nullable boolean | `isShared` |
| object | `location` with strings `city`, `country`, `district`, `province` |

`deviceStatus`: 0 inactive, 1 online, 2 offline, 3 shooting, 4 occupied. READ. An absent or
null value reads as 0; a number outside the list is handled as offline. READ. The device-detail
precheck before allocation refuses only offline; inactive, online, shooting and occupied all go
on to `online-link`. READ. OBSERVED (2026-10-12, sanitized field-type capture): `deviceStatus`
was an **integer** in both list and detail replies, including the detail replies during busy
windows. The word "occupied" in earlier observation notes is the status name, not the wire
value. A string here would make the app's Gson decode fail. INFERRED. `shareStartTime` and
`shareExpirationTime` were integers on the wire although declared as strings; Gson accepts this.
OBSERVED / INFERRED.

Member requirements (READ unless marked):

| Member | Absent or null in the app |
|---|---|
| `deviceSn` | Required. It is sent back in detail and `online-link`; a null breaks the record's hash (INFERRED) |
| `ssid` | Required. For a known model without an alias, a null `ssid` fails a not-null check; the error is caught and the **whole page** is marked failed (INFERRED from the code path). Meaning of a null `ssid` unresolved (server-side) |
| `deviceModel` | Tolerated: null becomes `""`, an unknown model shown as "--" |
| `deviceStatus` | Tolerated as 0 (inactive) |

Renaming refuses a blank serial, model or alias. READ.

R13b. A server MUST send `deviceSn`, `ssid` and an integer `deviceStatus` in every device record,
in both list and detail replies. A client MUST accept the integer form of `deviceStatus` and
SHOULD treat any other value as unknown. INFERRED.

## Allocation: `online-link`

```
GET /v1/device-p2p/online-link?deviceSn=<sn>&deviceModel=<model>&srcId=<client id>
```

`deviceSn` and `deviceModel` come from the device-detail reply of the precheck ([Device selection](#device-selection)), not
directly from the selected list record. READ (app 3.3.2). `srcId` is the app's
persistent per-installation identifier (created at first start; see
[account login](../account-login/lifecycle.md#storage-startup-and-source-identifier)), empty if never created. READ.

Successful `data` (READ, all eight members declared):

| Member | Type | Use |
|---|---|---|
| `deviceUid` | string | IOTC connection target (20-byte UID) |
| `sdkLicenseKey` | string | Installed in the SDK before connecting ([sdk-licence.md](sdk-licence.md)) |
| `p2pFactory` | string | No use found |
| `p2pLicenseKey` | string | No use found |
| `username` | string | Tunnel authentication callback |
| `password` | string | Tunnel authentication callback |
| `p2pStatus` | int | No use found |
| `conId` | string | Cloud attempt ID: reports and stop |

Requirements (READ): `data`, `conId`, `deviceUid`, `sdkLicenseKey`, `username` and `password`
are all used without a null check, so a server MUST send them, and a null in any of them ends the
attempt with an app exception. How the native SDK's JNI entry points behave on a null string varies by call. The JNI wrapper for
`IOTC_Connect_ByUID` null-checks the UID string before converting it and, on null, forwards a null
pointer to the native call. The wrapper for `P2PTunnelAgent_Connect_Ex` null-checks its string
argument first and returns -10000 on null (and -30021 on a null authentication object). The wrapper
for `TUTK_SDK_Set_License_Key` does **not** guard the string: it passes it straight to the JVM
string conversion, so a null licence is left to the JVM. Every wrapper that converts a string
returns -100000 when the conversion itself yields null. READ (app library, SDK 4.3.8).
`p2pFactory`, `p2pLicenseKey` and `p2pStatus` have no readers, so they MAY be absent or null.
OBSERVED (2026-10-12): all eight members present, `p2pStatus` an integer.

R14. The allocation carries no expiry or TTL member. The app does not pass `conId` or any
lease time to the SDK. READ. Lifetime and reuse rules of an allocation are unresolved (server-side); a client
MUST NOT assume an allocation stays valid after the transport is lost (see R2).

R15. `conId` is a cloud identifier, not an IOTC session number. READ.

## Reports and stop

**Connection report.** `POST /v1/device-log/report`, body (all strings): `deviceSn`, `event`,
`deviceModel`, `logInfo`, `conId`. `event` is one of `p2pConnectStart`, `p2pConnectSucceed`,
`p2pConnectFailed`, `p2pConnectCancel`, `p2pConnectTimeoutCancel`. `logInfo` is a JSON
**string** whose text is an object `{ "code": int, "source": string }`; it is not a nested
object. READ.

R16. The app sends `p2pConnectStart` asynchronously after a successful `online-link`, unless the
attempt was cancelled or replaced. READ. Whether the server requires reports is unresolved (server-side); a
client MAY send them.

**Stop.** `POST /v1/device-p2p/stop`, body `{ "conId": string }`. READ.

R17. On a deliberate disconnect a client SHOULD send stop with the current `conId` when one is
known. A failed stop does not block local teardown. READ (app behaviour). The stop request
carries the token current when it is sent, which after a credential replay differs from the
token that allocated the `conId`; the client keeps no allocation-to-token binding. READ. Whether
the server accepts stop under a token other than the allocating one is unresolved (server-side). The app's local
transport-loss recovery suppresses stop. READ. App triggers (READ, app 3.3.2): stop is sent from
the user's disconnect and switch-device actions and from the account screen's logout, which
disconnects first; a logout caused by a 401 or by the web view `logoff` call sends no stop, so
the allocation is left for the server to expire (INFERRED). OBSERVED (2026-10-12): an accepted stop shortens
the post-release busy window ([Observed single-session enforcement](#observed-single-session-enforcement)).

**Other support calls.** `POST /v1/my-device/reboot` with `deviceSn`, `deviceModel` (strings) is
a user-triggered recovery action, not part of allocation. `POST /v1/device-log/request-firmware-report`
takes strings `deviceModel`, `deviceSn`, `softwareBuild`, `osBuild`, `os`, `contact`,
`networkEnv`, `description`, `attachmentUrl` and a string list `imageUrl`; its `data` is untyped.
READ.

### Cloud and workflow error codes

App handling of connection failures (READ):

| Source | Code | Meaning used by the app |
|---|---:|---|
| Cloud / device status | 2, 300406 | Device offline |
| Cloud | 300403 | Remote service busy; retry later |
| Cloud | 300404 | Device already has a remote session; retry later |
| Cloud | 300405 | Suggest device restart |
| Cloud | other | Generic failure |
| Native | -48 | Suggest device restart |
| Native / workflow | -42, -10087 | Suggest changing mobile network (-10087 is the app's own timeout) |
| Native | -30002 | Port in use; suggest restarting the app (the engine retries once first) |
| Workflow | -10086 | Cancelled; no prompt |
| Native / workflow | -1 | Generic failure |

R18. No numeric cooldown or `Retry-After` handling exists in these branches. A one-second delay
on a test screen is not a service limit. READ. A client MUST NOT invent a cooldown from it.

## Observed single-session enforcement

OBSERVED (2026-10-12, from sanitized logs of 2026-10-10/11; one account, one device, same
credentials throughout; firmware not matched to 9.31):

- Every busy refusal came from the cloud. No IOTC, RDT or tunnel-login error was seen in a busy
  case.
- Allocation refused: HTTP 400, code 300404, 22 of 22 refusals in one series. After a release
  the first successful allocation came about 35–41 s after the release began, and the connection
  was usable about 43–50 s after it. Faster retries did not shorten this.
- Device detail during the window: HTTP 200, envelope code 200, `deviceStatus` occupied (integer 4
  on the wire; see [Device selection](#device-selection)); seen
  after an accepted stop and during idle-release redials (six refusals, then success about 45 s
  after an idle release).
- With an accepted stop, the busy window after a client kill ended at +26 to +38 s (3 of 3);
  without stop, +50 to +62 s (3 of 3), with a 10 s redial cadence.
- Codes 300403 and 300406 were not seen on a dial.
- Multiplexing inside one tunnel session works: four simultaneous JSON-RPC clients on port 4700,
  fifty sequential ones, a persistent 4700 loop (902/902 replies over 25 min) beside a second
  client, sixteen concurrent file streams (about 1 GB at 8.2 MB/s aggregate) beside it, seven
  parallel HTTP requests to port 80, and tunnel channel IDs reaching 58 in one session. Failures
  under load were client receive limits, not device limits.

INFERRED: an accepted stop does not clear occupancy at once; the cloud appears to wait for the
device side to report the session gone (possibly an IOTC timeout). Not proven.

Not observed: a second allocation while a session is live; busy while the vendor app holds the
session (an older note claims it, without the code); whether the limit is per account, device or
credential.

R19. A client SHOULD treat 300404 (and `deviceStatus` 4, occupied) as "retry later", SHOULD send stop on
orderly release, and SHOULD expect a window of roughly 30–60 s before a new allocation succeeds.
OBSERVED (values) / INFERRED (rule). A client SHOULD NOT redial faster than about every 10 s.
INFERRED (rule); OBSERVED (2026-10-12): more frequent retries did not shorten the window, and the
measured series used a 10 s cadence.

### `srcId` stability and the busy window

OBSERVED (2026-10-12; orderly release with an accepted stop): a redial with the same `srcId` and
a redial with a newly generated `srcId` both became ready about 36 s after the release (35.7–36.7
s; 37.5–39.3 s from the previous allocation), each after six busy precheck replies and seven
dials. No difference between the two, and no extra delay near 70 s. Allocation took about 5 s
from launch in both.

READ (device firmware 9.31, both builds; remote manager "P2P server already started" handler): a control request with the same UID and the same `srcId` clears the old
tunnel sessions; the same UID with a different `srcId` is refused ("busy2") while under 70 s have
elapsed **or** the old session is still connected; a different UID restarts the tunnel server.
READ (device firmware 9.75, both builds; 64-bit handlers for the different-`srcId` and
already-started cases): the gate is 65 s instead of 70 s, and it still requires that no P2P
session is connected. The same-`srcId` clean-up and the different-UID restart are unchanged; the
only other difference in that handler is a corrected log string. The 70 s gate
(65 s in firmware 9.75; the occupy-timeout thread's sleep has the same values, see
[device-cloud-link.md R46n](device-cloud-link.md#p2p-monitor-and-occupy-timers)) is not an allocation lifetime, and the clean-up on a matching request does not show
that a new native connection by itself retires the old session.

INFERRED: under orderly release the cloud gate, not the device check, produces the busy replies,
and that gate does not depend on `srcId`; consistent with the cloud serializing allocations per
device, not proven. Not observed: an unclean exit of the previous client, or a redial while the
old tunnel is still connected, which is where the firmware reading predicts a `srcId` effect.

R20. A client MUST keep a stable `srcId` across its own reconnects. INFERRED (from the device
handler: a changed `srcId` is refused while under 70 s (firmware 9.31) or 65 s (firmware 9.75)
have elapsed or the old session is still connected). The OBSERVED series above predates firmware
9.75 and was taken on firmware 9.31.

## Optional remote-feature catalogue

The remote API interface has 24 methods: the seven above (`my-device`, `my-device/detail`,
`online-link`, `stop`, `device-log/report`, `reboot`, `request-firmware-report`) and the 17
below. READ. These are not needed to open a tunnel. A declaration shows verb, path, query and body
type only; server authorization rules, response contents and units are unresolved (server-side).

| Verb and path | Purpose (app method) | Query or body members |
|---|---|---|
| POST `/v1/my-device` | add device | `address`, `deviceModel`, `deviceSn`, `latitude`, `longitude`, `ssid`, `status`, `subModel` |
| POST `/v1/my-remote-location` | change remote location | same members as add device |
| POST `/v1/my-device/alias` | rename | `deviceAlias`, `deviceModel`, `deviceSn` |
| POST `/v1/my-device/share` | add share user | `deviceModel`, `deviceSn`, `shareExpirationTime`, `shareStartTime`, `shareUser` |
| GET `/v1/my-device/share` | list share users | query `deviceSn`, `deviceModel` |
| GET `/v1/my-device/check-share` | check share | query `deviceSn`, `deviceModel` |
| POST `/v1/my-device/remove-share` | remove share users | `deviceModel`, `deviceSn`, `shareUserIds` (string list) |
| POST `/v1/device-online/report` | report join result | `deviceModel`, `deviceSn`, `status` |
| POST `/v1/device-transfer/send-code` | send transfer code | `deviceModel`, `deviceSn`, `type` (enum) |
| POST `/v1/device-transfer/verify-code` | verify transfer code | `code`, `deviceModel`, `deviceSn` |
| POST `/v1/device-transfer/request` | request transfer | `code`, `deviceModel`, `deviceSn`, `toUser` |
| GET `/v1/device-transfer/list` | list transfers | query `current`, `pageSize` |
| GET `/v1/device-transfer/detail` | transfer detail | query `transferId`, `deviceSn`, `deviceModel` |
| POST `/v1/device-transfer/approve` | approve | `transferId` |
| POST `/v1/device-transfer/reject` | reject | `transferId` |
| POST `/v1/device-transfer/cancel` | cancel | `deviceModel`, `deviceSn` |
| POST `/v1/lbs/reverse-geocode` | reverse geocode | `language`, `latitude`, `longitude`, `radius`, `returnPoi` |

The iOS app 3.4.0 network framework adds three remote endpoints, mapped from its API-name table to
the URL table (READ). The disconnect-device API posts to `/v1/device-p2p/retrieve` (this resolves
the earlier INFERRED mapping), the stop-connect API uses `/v1/device-p2p/stop` (the stop call of
[Reports and stop](#reports-and-stop)), and the remote-unbind API posts to `/v1/my-device/remote-unbind`. Both new APIs report
POST as their method (the literal method value is READ; that it means POST is INFERRED by analogy
to other write-action APIs in the same table, no literal "POST" name was found bound to it) and
send a body of exactly `deviceSn` and `deviceModel` (both strings; READ from the two APIs'
property lists in the iOS network framework). Neither API has a visible caller anywhere in the
app's unencrypted frameworks; the call site is presumably in the app's main executable, which is
copy-protected and out of reach of static analysis. Confirmed-present-but-not-visibly-called.
INFERRED (reachability).

Response handling differs between the two (READ, from the iOS network framework):
- Disconnect-device: the success path reads `data.result` from the envelope (so the full shape
  consumed is `{"data": {"result": <bool-ish>}}`) and treats it as a boolean. There is no
  endpoint-specific error-code mapper; a failure surfaces the generic HTTP error and message
  unchanged.
- Remote-unbind: the success path passes the whole `data` value through with no further key
  extraction, so its shape beyond "whatever `data` contains" is unresolved. On success the app
  posts a local notification named for "remote unbind succeeded". Failures funnel through an
  endpoint-specific mapper that recognizes exactly three codes in the inclusive range
  400002-400021: 400002, 400020 and 400021 are flagged/wrapped (kept as the same numeric value,
  not remapped); every other code in or outside that range is forwarded unchanged. The meaning of
  400002/400020/400021 is unresolved: no string table in the framework ties them to text.

The server effect of either call and whether the Android app has equivalents remain unresolved
(server-side).

Member types (READ): share times and the body `transferId` are 64-bit integers, while the
detail query `transferId` is a nullable 32-bit integer; coordinates are nullable doubles;
`status`, `radius`, `returnPoi` are nullable integers; others are strings unless noted. Enum and
null encoding follow R10: `type` is `email` or `mobile`, and null members (the app's add-device
call leaves `status` null) are omitted. READ (app 3.3.2). Server-side units and how the server
treats omitted members are unresolved (server-side).
