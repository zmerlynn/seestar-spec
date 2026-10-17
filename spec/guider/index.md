# Guider process

This chapter covers the guider process: its JSON command/event server on TCP 4400, its image
server on TCP 4500, its serial-bridge listeners on TCP 4040 and 4030, how the imager connects to it and relays commands and events, the guider
parser and reply rules, its events, and the guiding workflow. Below it sit the mount serial
link and the guide camera; its raw serial bridge is in [serial-bridge.md](serial-bridge.md).
Above it sits the imager's control stream on TCP 4700 (see
[../control/session-handshake.md](../control/session-handshake.md) and
[../control/events-overview.md](../control/events-overview.md)). Per-method detail:
`catalog/guider/`; generated cards: `docs/guider/`.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients; sentences about what "the device" or "the guider" does are descriptions.

Labels follow `CONVENTIONS.md`: **READ** (static analysis of firmware 9.31 or app 3.3.2),
**OBSERVED** (seen on a device, date given), **INFERRED**, **unresolved**. READ says what the
code does, not that the camera or mount then succeeds. Claims are for the 64-bit guider build
unless stated; the 32-bit build registers the same tables and was checked for seven mount
paths only ([Build differences](#build-differences)). No guider request was ever sent to a device.

Basis for the whole chapter: static analysis of firmware 9.31 (guider, imager and updater
ELFs) and app 3.3.2.

## Endpoints

The guider process opens four listeners at startup. READ.

| Port | Listener | Content |
|---|---|---|
| TCP 4400 | command/event server | JSON requests, replies and unsolicited events (this chapter). |
| TCP 4500 | image server | Guide-camera images in binary frames (R1a). |
| TCP 4040 | serial-bridge control server | JSON `set_settings` and `disconnect`; requires the client-auth step; see [serial-bridge.md](serial-bridge.md). |
| TCP 4030 | raw serial bridge (ser2net) | Bytes to and from the mount serial device; admission gated by 4040; see [serial-bridge.md](serial-bridge.md). |

R1. The 4400 server dispatches one main command table of about 105 method names. READ. A
second, separate table (`set_settings`, `disconnect`) controls the serial bridge; its names
are not part of the 4400 command set and are not relay targets. READ. The table belongs to the
guider's ser2net control server, not to the 4400 server. READ. That control server listens on
TCP 4040, a shared JSON server that requires the client-auth step. At startup it starts before
the 4030 bridge. READ. TCP 4030 carries raw bridge bytes. It admits a client only when that
client's IP has passed verification on 4040, or in factory mode, and it drops 4030 connections
when that verification is revoked. READ. A client MUST authenticate on 4040 before opening
4030. See [serial-bridge.md: Control table](serial-bridge.md#control-table).

R1a. TCP 4500 serves guide-camera images. Only `test_connection`, `begin_streaming` and
`stop_streaming` are registered. Requests are JSON texts with `id` and `method`. READ. Every
reply and every pushed image starts with an 80-byte header, in this order: a 32-bit
little-endian magic (see [ports.md: Guider image server (4500)](../transport/ports.md#guider-image-server-4500)), a
big-endian 16-bit header length (80), a big-endian 32-bit payload length, a payload-type byte at offset 14
(1 for a text reply) and the low byte of the request `id`. READ. This differs from the
imager's image sockets, which mark a text reply with imgType 0 at offset 13 and put dataType 0
(ok) or 1 (error) at offset 14, so an ok text reply carries 0 there
([../media/image-sockets.md: Reply framing](../media/image-sockets.md#reply-framing)). READ (both). Image payloads carry
big-endian 16-bit width, height and star position. READ. After `begin_streaming` the guider
fetches the guide image about every 500 ms, with a star crop, and pushes one framed image to
each subscribed socket until `stop_streaming` or disconnect. READ. A malformed request gets a
short text reply, not a numeric code: `can't parse`, `can't find method field`, `invalid method
type`, `can't find id field`, `invalid id type` or `unknown mothod` (spelled so). READ. The
base header is the imager's 80-byte image-socket header
([../media/image-sockets.md R10a](../media/image-sockets.md#reply-framing)). READ. Compared
field by field with the imager's header (64-bit; 32-bit not checked), offsets 0 to 19 have the same
meaning (magic, version, header length, payload length, first and last payload byte, byte 12,
imgType, dataType, id byte, width, height), except that dataType is 2 for any image payload and
never 3: the guider does not compress. READ. The rest differs:

| Offset | Size | Guider meaning | Label |
|---:|---:|---|---|
| 20 | 2 | guide-star x, 0xFFFF (-1) when no star is locked | READ |
| 22 | 2 | guide-star y, 0xFFFF (-1) when no star is locked | READ |
| 24 | 2 | 1 when the value at offset 30 is positive, else 0 | READ |
| 26 | 2 | width of a second image, or 0 | READ |
| 28 | 2 | height of a second image, or 0 | READ |
| 30 | 2 | the locked star's HFD × 100, 0 when no star is locked | READ |
| 32 | 2 | number of stars in the star list, or 0 when there is at most one star | READ |
| 34 | 46 | 0 | READ |

All are big-endian 16-bit. The payload is the guide image, then the second image when its size
is non-zero, then the star list when the count at offset 32 is non-zero: 6 bytes per star as
three little-endian 16-bit values (not byte-swapped, unlike the header). READ. The third star value is
the HFD × 100 for the first entry and 1000 for every further entry. READ (64-bit; 32-bit not
checked). A client SHOULD NOT read offsets 20 to 29 with the imager's
meanings (hfdX, hfdY, hfd, canDebayer, image id) on 4500. INFERRED.

R2. On every accepted 4400 connection the guider sends a [`Version`](../../docs/control/events/Version.md) greeting to that socket
only, before any request. It carries `Event`, `Timestamp` and `name` (the literal
`ASI AIR guider`); it does not carry the imager's firmware-version members. READ.

```text
{"Event":"Version","Timestamp":"1234.123456789","name":"ASI AIR guider"}
```

### Framing

The guider uses the same JSON socket server class as the imager. INFERRED: framing is
therefore the imager's: each JSON text is one line; the device writes CRLF after each reply
and event; the reader splits input on CR or LF independently.

R3. A client MUST send each request as one line terminated by LF or CRLF, and MUST NOT
pretty-print requests over several lines. INFERRED (from the shared server class).

## How the imager reaches the guider

The imager process is the guider's normal client. On startup it builds a guider client that
connects to TCP 4400 on the local host and installs a line reader on that socket. READ.

```text
 app                      imager (TCP 4700)                 guider (TCP 4400)
  |                             |      connect, Version greeting  |
  |                             |<--------------------------------|
  |                             |-- speed_move_ratio (reconnect)->|
  | {"id":7,"method":"loop"}    |                                 |
  |---------------------------->|                                 |
  |                             | own table: no match (code 103)  |
  |                             |-- original request text ------->|
  |                             |<-- reply line ------------------|
  |<-- reply (parsed back) -----|                                 |
  |                             |<-- {"Event":"LoopingExposures"..|
  |<-- same event line ---------|                                 |
```

### Command relay

R4. The imager relays a request to the guider only when all of these hold. READ:

1. the method is not in the imager's own command table (the imager would otherwise answer
   with its own handler; there is no per-name allowlist);
2. the requester was dispatched through the imager's main table, not the guest table. The
   guest table is chosen when guest mode is on, a guest table exists, and the client is
   neither the master nor a local/internal connection; that path disables relay;
3. the request is a single command, not an element of a JSON-RPC batch (batch handling is a
   separate branch; relay inside a batch is not guaranteed).

R5. The imager forwards the **original request text** unchanged and waits up to 10000 ms for
the guider's reply, whose text it sends back to the requester unchanged, without parsing it. READ. The reply a client
receives on 4700 for a timeout, a failed connection or an unparsable guider reply is
specified in [mount-and-motion.md R3](../control/mount-and-motion.md#where-a-call-is-executed); clients MUST treat a missing reply as unknown outcome.

R6. Image/file methods and the serial-bridge table are never relay targets: the relay only
reaches the 4400 command table. READ.

R7. **Reconnect side effect.** While handling a relayed request the imager may first
(re)connect to the guider. Its connect callback sends `speed_move_ratio` to the guider
(updating the guider's motion scaling), refreshes the mount mode and may reapply power-LED
settings. READ. Hence even a pure getter sent through the relay can have a state-changing
effect (tier C). A client that needs observation-only behaviour SHOULD NOT assume an earlier
successful request proves the link is stable. INFERRED.

R8. A client MAY instead connect to TCP 4400 directly. INFERRED. The guider server has no
guest/main split in the evidence. INFERRED. Port 4400 is in the client-auth port set of the
shared JSON server code ([ports.md](../transport/ports.md)); the guider's copy lists 4040, 4400
and 4700 to 4702. READ. That the guider's copy
applies the same step to external clients is INFERRED; a direct client SHOULD expect to have to
verify as on 4700. The imager's own connection is local and is treated as verified. READ. The
guider has its own equivalent of the imager's idle checker. READ. That its threshold is also
15 s is INFERRED.

### Event forwarding

R9. The imager's guider line reader tests each incoming line for the exact substring
`"Event":"`. A matching line is broadcast unchanged to all 4700 clients. READ. The test is
lexical: a line with whitespace around the colon would not be forwarded. Replies (lines
without that substring) are delivered only to the waiting relay.

R10. The auxiliary (wide-camera) imager process also connects to the guider but suppresses
forwarding of 4400 events, so 4700 clients see one copy. READ.

R11. The imager additionally consumes some guider events itself ([`MoveByAngle`](../../docs/guider/events/MoveByAngle.md),
`GuideStarLostTooMuch`, [`MountConnection`](../../docs/guider/events/MountConnection.md), [`AutoOpenCamera`](../../docs/guider/events/AutoOpenCamera.md), [`AppStateChange`](../../docs/control/events/AppStateChange.md), [`MountMode`](../../docs/guider/events/MountMode.md)).
Consuming them does not change the forwarded wire line. READ.

## Requests and parameter parsing

Requests use the common envelope: `id` (integer or string, echoed), `method` (string),
optional `params`. READ.

Handlers bind parameters through a few shared helpers. Their rules apply to every method that
uses them; each card says which form a method accepts. READ:

R12. **Object or positional.** Most handlers with named parameters accept either an object
(`{"ra":10.5,"dec":20}`) or an array in the documented positional order (`[10.5,20]`). Scalars
are not bound to a name. Unknown object keys are ignored.

R13. **Object-only.** `scope_speed_move`, `speed_move_ratio` and `scope_fine_move` build their
parameter map by hand and read named object members only. A client MUST send these as objects.

R14. **Single-value unwrap.** Handlers taking one unnamed value (for example `set_exposure`)
accept the scalar or an array and use its first element. With a name, the helper can select
that member from an object. Hence `[true]` and `[{"tracking":true}]` are not interchangeable.

R15. **Numbers.** The number helper accepts JSON integers and reals. Reals pass through 32-bit
float precision before widening. Handlers that test for an integer directly reject reals such
as `1.0` (code 104).

R16. **Booleans.** The boolean helper accepts `true`/`false` or an integer (nonzero is true).
Some handlers test for a JSON boolean directly and reject integers (code 106), for example
`set_all_connected` and the member tests in `set_connected`. A client SHOULD always send JSON
booleans.

R17. Handlers rarely range-check or clamp. A client MUST keep values in sane ranges itself.
READ (absence of checks in the inspected handlers).

Malformed JSON gets 101. READ. Duplicate members are kept: at the top level the last `id`,
`method` and `params` win, while some handlers keep the first duplicate inside `params`. READ
(top level and the handlers inspected) / INFERRED (every handler). Integers are parsed into 32
bits and wrap silently. READ. A client MUST NOT send duplicate keys or integers outside the
signed 32-bit range. Limits on string and line length are unresolved.

## Replies

R18. A success reply carries `result` and `code` 0. An error reply carries an `error` string
and a nonzero `code`, and no `result`. The outer layer adds `method`, `id`, `jsonrpc` and
`Timestamp`. READ. As on the imager, receivers MUST NOT depend on member order and MUST NOT
require `jsonrpc` or `Timestamp`.

R19. A reply means the handler, or the worker start it triggered, returned. It never means
the physical operation completed (a slew arrived, guiding settled). READ. Completion is
signalled, if at all, by events ([Events](#events)).

R20. The error string is looked up from the code; an unknown code yields `fail to operate`.
READ (shared lookup). A table entry does not mean a method can emit that code; each card lists
the codes its handler sets explicitly. Native and driver codes forwarded from lower layers are
not exhausted by the cards.

Codes set explicitly by guider handlers, with their labels. READ:

| Code | Label | Code | Label |
|---|---|---|---|
| 102 | invalid params | 268 | operation is in progress |
| 104 | expected int param | 300 | internal error |
| 105 | expected string param | 303 | could not start looping |
| 106 | expected bool param | 304 | could not set lock position when calibrate or guide |
| 107 | expected object param | 305 | could not set lock position |
| 108 | expected float param | 312 | cannot select if equipment are connected |
| 109 | unexpected param | 315 | mount is not connected |
| 202 | already connected | 316 | could not find star |
| 203 | equipment is moving | 318 | device not connected |
| 204 | out of limit | 319 | cannot issue guide pulse while calibrating or guiding |
| 207 | fail to operate | 320 | move failed |
| 209 | invalid value | 321 | history is empty now |
| 210 | not supported | 322 | could not set param |
| 216 | fail to set timezone | 323 | could not get param |
| | | 536 | view plan is already running |

`set_all_connected` also fails with 201 on a connection failure; its label was not recovered.
Dispatcher-level codes on 4400: unparseable text gives 101 (`invalid JSON request` with the
parser's reason). A request without `id`, an empty object, or text that is not an object gives
200 (invalid id). A request without a string `method` gives 100 (invalid request); a
non-string `method` counts as missing. An unregistered method gives 103 (method not found).
READ. A client MUST always send an `id`. The 4500 server answers with text instead (R1a).

## Events

Guider events use the common envelope: top-level `Event` and `Timestamp` strings, then
event members. `Timestamp` is monotonic seconds with nine fraction digits, not a calendar
time. There is no `id`, `method` or `jsonrpc`. READ. Ordinary guider events go to every
connection of the 4400 server and are forwarded to 4700 ([How the imager reaches the guider](#how-the-imager-reaches-the-guider)). READ.

R21. Guider events follow three payload styles, which a client MUST NOT mix up. READ:

1. **Guiding notifications (custom).** Members are capitalised (`Mount`, `X`, `State`,
   `Frame`) and capitalisation is significant. There is no lowercase `state`.
2. **Bare notifications.** `Event` and `Timestamp` only.
3. **Function events.** Mount workers named [`ScopeGoto`](../../docs/control/events/ScopeGoto.md) and [`ScopeHome`](../../docs/guider/events/ScopeHome.md) report through the
   function-event formatter: `state` is one of `idle`, `working`, `complete`, `fail`,
   `cancel`; `code` and `error` appear on `fail`; `lapse_ms` and an optional `route` array
   may appear. Other mount events ([`ScopeTrack`](../../docs/guider/events/ScopeTrack.md), `MountMode`, `MoveByAngle`,
   `MountConnection`, [`AutoCloseMount`](../../docs/guider/events/AutoCloseMount.md), `AutoOpenCamera`, [`Temperature`](../../docs/guider/events/Temperature.md)) have their own
   members. See the cards.

Guiding events and their members. READ (member names and types); units INFERRED where marked:

| Event | Members | Meaning |
|---|---|---|
| [`LoopingExposures`](../../docs/guider/events/LoopingExposures.md) | `Frame` int | one guide-camera loop frame |
| [`LoopingExposuresStopped`](../../docs/guider/events/LoopingExposuresStopped.md) | - | loop capture stopped |
| [`StarSelected`](../../docs/guider/events/StarSelected.md) | `X`, `Y` number | guide star selected (pixels) |
| [`StarPos`](../../docs/guider/events/StarPos.md) | `X`, `Y` number | new measured star position |
| [`LockPositionSet`](../../docs/guider/events/LockPositionSet.md) | `X`, `Y` number | lock position changed |
| [`LockPositionLost`](../../docs/guider/events/LockPositionLost.md) | - | lock target lost |
| [`StartCalibration`](../../docs/guider/events/StartCalibration.md) | `Mount` string | calibration begins |
| [`Calibrating`](../../docs/guider/events/Calibrating.md) | `State` string | calibration step text |
| [`CalibrationComplete`](../../docs/guider/events/CalibrationComplete.md) | `Mount` string, `Limit` [int,int] | calibration done |
| [`CalibrationFailed`](../../docs/guider/events/CalibrationFailed.md) | `Mount`, `Reason` string | calibration failed |
| [`CalibrationDataFlipped`](../../docs/guider/events/CalibrationDataFlipped.md) | `Mount` string | calibration flipped for a pier-side change |
| [`StartGuiding`](../../docs/guider/events/StartGuiding.md) | - | guiding begins |
| [`GuideStep`](../../docs/guider/events/GuideStep.md) | see below | one guiding correction frame |
| [`GuidingDithered`](../../docs/guider/events/GuidingDithered.md) | `dx`, `dy` number | dither offset applied (pixels INFERRED) |
| [`SettleBegin`](../../docs/guider/events/SettleBegin.md) | - | settling starts |
| [`Settling`](../../docs/guider/events/Settling.md) | `Distance`, `Time`, `SettleTime` number; `StarLocked` bool | settle progress (pixels, seconds INFERRED) |
| [`SettleDone`](../../docs/guider/events/SettleDone.md) | `Status` int (0 success); `Error` string on failure; `TotalFrames`, `DroppedFrames` int | settle finished |
| [`StarLost`](../../docs/guider/events/StarLost.md) | `Frame` int; `Time`, `StarMass`, `SNR`, `AvgDist` number; `Status` string; `ErrorCode` int | a frame lost the star |
| [`GuideStarLostTooMuch`](../../docs/guider/events/GuideStarLostTooMuch.md) | - | star-loss threshold crossed |
| [`Paused`](../../docs/guider/events/Paused.md) / [`Resumed`](../../docs/guider/events/Resumed.md) | - | guiding paused or resumed |
| [`GuidingStopped`](../../docs/guider/events/GuidingStopped.md) | - | guiding stopped |
| [`AppState`](../../docs/guider/events/AppState.md) | `State` string | guider application state |
| [`INDIServer`](../../docs/guider/events/INDIServer.md) | `Msg` string | INDI server message |

`GuideStep` members: `Frame` int; `Time` number (not the envelope Timestamp); `Mount` string;
`dx`, `dy` number; `RADistanceRaw`, `DECDistanceRaw`, `RADistanceGuide`, `DECDistanceGuide`
number;
`RADuration`, `DECDuration` int (milliseconds INFERRED); `RADirection`, `DECDirection`
string; `IsSettle`, `IsDither` int 0 or 1 (not bool); `StarMass`, `SNR`, `AvgDist` number; `RALimited`,
`DecLimited` bool (when set); `ErrorCode` int; `Pos` [int,int] or null. READ.

`Time` is seconds (three decimals) since guiding started. READ (format) / INFERRED (origin and
unit). `dx` and `dy` are raw camera pixels, read and serialized with no scaling. `RADistanceRaw`
and `DECDistanceRaw` are, despite the name, the pair that *is* converted: the same pixel pair the
function also uses elsewhere is multiplied once by the guide camera's arcseconds-per-pixel scale,
and these two members hold that product, in arcseconds. `RADistanceGuide` and `DECDistanceGuide`
are a separate pair, not converted in this function; their scale is probably pixels. READ
(conversion and which members get it, address-verified in the 9.31 build); INFERRED (final unit
of the two unconverted pairs). `IsSettle` and `IsDither`
are always present (READ); `IsDither` is a one-shot flag cleared when reported (READ), set by a
dither (INFERRED). `RADuration` with
`RADirection`, and `DECDuration` with `DECDirection`, are present only when that axis has a
positive correction duration. READ. `StarMass` is written unscaled; its scale is unresolved.

R22. Events are sent on transitions or per frame; there is no periodic timer and no rate cap.
READ. Event delivery, ordering against the command reply and ordering across worker threads
are not guaranteed. A client MUST NOT assume the reply arrives before the first event, and
MUST correlate by event name and content, not by arrival order. READ / INFERRED.

## Chapter map

| File | Contents | Rules |
|---|---|---|
| this file | Endpoints, imager relay and event forwarding, parameter parsing, replies, events, method groups, build differences. | R1 to R22 |
| [guiding.md](guiding.md) | Guiding workflow (preconditions, states, methods, typical sequence), the guider's mount, time and other commands, and the imager's dither settings (`get_dither`, `set_dither`). | R23 to R38 |
| [serial-bridge.md](serial-bridge.md) | The guider's raw serial bridge. | own numbering |
| [mount-serial-commands.md](mount-serial-commands.md) | The mount serial command set: framing, command table, `scope_*` mapping, goto sequence, status flags and limits, version gates, startup motor-current check, firmware 9.75 deltas. | own numbering |

## Method groups

Tier letters are the cards' side-effect tiers (A request-local, B observation-safe, C changes
state, D not established), for the native handler; relay can add C (R7).

| Group | Methods |
|---|---|
| Equipment | [set_connected](../../docs/guider/methods/set_connected.md) C, [set_all_connected](../../docs/guider/methods/set_all_connected.md) C, [get_connected](../../docs/guider/methods/get_connected.md) D, [set_camera_idx](../../docs/guider/methods/set_camera_idx.md) C, [select_serial_dev](../../docs/guider/methods/select_serial_dev.md) C, [mount_scan_port](../../docs/guider/methods/mount_scan_port.md) B, [get_mount_list](../../docs/guider/methods/get_mount_list.md) B, [select_mount_list_index](../../docs/guider/methods/select_mount_list_index.md) C, [get_mount_index](../../docs/guider/methods/get_mount_index.md) A |
| Camera | [set_exposure](../../docs/guider/methods/set_exposure.md) C, [get_exposure](../../docs/guider/methods/get_exposure.md) A, [set_gain](../../docs/guider/methods/set_gain.md) C, [get_gain](../../docs/guider/methods/get_gain.md) A, [set_camera_binning](../../docs/guider/methods/set_camera_binning.md) C, [get_camera_binning](../../docs/guider/methods/get_camera_binning.md) A, [set_search_region](../../docs/guider/methods/set_search_region.md) C, [get_search_region](../../docs/guider/methods/get_search_region.md) A, [get_pixel_scale](../../docs/guider/methods/get_pixel_scale.md) A, [get_dark_info](../../docs/guider/methods/get_dark_info.md) D, [get_func_state](../../docs/guider/methods/get_func_state.md) A |
| Guiding | [loop](../../docs/guider/methods/loop.md) C, [stop_capture](../../docs/guider/methods/stop_capture.md) C, [find_star](../../docs/guider/methods/find_star.md) C, [deselect_star](../../docs/guider/methods/deselect_star.md) C, [set_lock_position](../../docs/guider/methods/set_lock_position.md) C, [get_lock_position](../../docs/guider/methods/get_lock_position.md) A, [guide](../../docs/guider/methods/guide.md) C, [dither](../../docs/guider/methods/dither.md) C, [set_paused](../../docs/guider/methods/set_paused.md) C, [get_paused](../../docs/guider/methods/get_paused.md) A, [guide_pulse](../../docs/guider/methods/guide_pulse.md) C |
| Calibration and algorithm | [clear_calibration](../../docs/guider/methods/clear_calibration.md) C, [flip_calibration](../../docs/guider/methods/flip_calibration.md) C, [get_calibrated](../../docs/guider/methods/get_calibrated.md) A, [get_flip_calibration](../../docs/guider/methods/get_flip_calibration.md) A, [set_auto_load_calibration](../../docs/guider/methods/set_auto_load_calibration.md) C, [get_auto_load_calibration](../../docs/guider/methods/get_auto_load_calibration.md) A, [set_dec_guide_mode](../../docs/guider/methods/set_dec_guide_mode.md) C, [get_dec_guide_mode](../../docs/guider/methods/get_dec_guide_mode.md) A, [set_algo_param](../../docs/guider/methods/set_algo_param.md) C, [get_algo_param](../../docs/guider/methods/get_algo_param.md) D, [get_algo_param_names](../../docs/guider/methods/get_algo_param_names.md) D, [get_ra_dec_history](../../docs/guider/methods/get_ra_dec_history.md) A, [clear_ra_dec_history](../../docs/guider/methods/clear_ra_dec_history.md) B, [get_ra_dec_angle](../../docs/guider/methods/get_ra_dec_angle.md) A |
| Mount | the `scope_*` methods (see `docs/guider/methods/`), [can_goto](../../docs/guider/methods/can_goto.md) A, [clear_az_state](../../docs/guider/methods/clear_az_state.md) C, [speed_move_ratio](../../docs/guider/methods/speed_move_ratio.md) C, [get_user_location](../../docs/guider/methods/get_user_location.md) D, [set_user_location](../../docs/guider/methods/set_user_location.md) C, [scope_get_test_date](../../docs/guider/methods/scope_get_test_date.md) D, [pi_set_time](../../docs/guider/methods/pi_set_time.md) C |
| Process | [shutdown](../../docs/guider/methods/shutdown.md) C |

Methods registered only in the guider table are catalogued under `guider`, even when the app
sends them on 4700 and they reach the guider by the code-103 relay (for example `pi_set_time`
and `set_user_location`).

## Build differences

The 32-bit guider build registers the same tables. Independent 32-bit checks confirm the
state-changing mount paths of `scope_goto`, `scope_speed_move`, `scope_park`,
`scope_set_track_state`, `scope_get_ra_dec`, `scope_sync` and `pi_set_time`. READ. The 32-bit
guider uses the same ports (4040 control, 4030 bridge) and the same client-auth port set, and
its strings show the same image-server methods, serial defaults, pause, star-loss and parser
messages. READ. Instruction-level parity of parameter parsing, defaults, error codes and
`GuideStep` scaling is not established; calibration `Limit` details are not established for
32-bit either. unresolved.

## Open questions

- Admission policy on 4400 for a direct (non-imager) client; whether several clients are
  supported and whether they all receive events.
- Complete, branch-qualified event set and ordering for `guide`, `dither`, `stop_capture`,
  `set_paused` and `deselect_star`.
- Units: `StarLost` `Time`, the four `GuideStep` distance members and star mass.
- Limits on string and line length in the parser.
- `AppState` values; `Calibrating.State` values.
- Instruction-level 32-bit parity ([Build differences](#build-differences)).
- Whether each Seestar model activates all retained guider functions (the guider is derived
  from a general astronomy-camera product).
