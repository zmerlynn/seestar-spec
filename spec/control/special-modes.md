# Special modes: Sun, Moon and planets, tracking, recording, streaming, functions

This chapter covers control-channel operations that run as long-lived device "functions" outside
ordinary deep-sky stacking: Sun/Moon/planet scan, sync and stacking, object tracking,
demonstration mode, AVI recording, AVI playback to the stream, and the generic function tree
with `start_func`, `stop_func` and `is_func_work`. The event envelope and the function-event
family sit below it ([events-overview.md](events-overview.md),
[events/families.md](events/families.md)). Plans that start these functions are in
[plan-scheduling.md](plan-scheduling.md). Sky positions are in
[object-lists.md](object-lists.md). Planet stacking, recording and playback, and demonstration
mode are specified in more detail in [stacking.md](stacking.md#planet-stack),
[../media/video.md](../media/video.md#avi-and-mp4-recording) and
[maintenance.md](maintenance.md#demonstration-mode-and-sound); those chapters are primary
where they overlap with this one.

App names: “Solar”, “Lunar” (“Moon Mode”) and “Planetary” are the Sun, Moon and planet modes (the
Android app uses one “Solar System” mode with a target type). “Sun/Moon Auto-center” is
`planet_correction`. “Smart Track” is object tracking (`start_track_object`). Names are the English
strings of iOS app 3.4.0; links are READ (app call sites) unless marked.

Basis for the whole chapter: static analysis of firmware 9.31 (64-bit build; 32-bit build
probable) and app 3.3.2, unless a line says otherwise.

## Conventions

RFC 2119 / RFC 8174 key words bind clients. Labels **READ**, **OBSERVED(date)**, **INFERRED** and
**unresolved** are as in [CONVENTIONS.md](../../CONVENTIONS.md). Error codes and messages are
those of the common error table.

View modes used below: 0 star, 1 scenery, 2 moon, 3 sun, 4 planet, 5 solar_sys, 6 none. READ.

## The function tree

The device runs each long operation as a named function: a worker thread with a state record.
Functions form a tree (for example `ViewPlan` > `Target` > lower work). READ.

### Function states

| Code | `state` string | Meaning |
|---|---|---|
| 0 | `idle` | not started |
| 1 | `working` | running |
| 2 | `complete` | ended normally |
| 3 | `fail` | ended with an error |
| 4 | `cancel` | stopped by request |

All rows READ. Unknown codes serialize as `idle`. READ.

```text
            start                 worker ends ok
  idle ---------------> working ----------------> complete
                          |  \
             worker error |   \ stop flag set (stop_func, stop_*)
                          v    v
                        fail  cancel
```

| From | Event | To | Label |
|---|---|---|---|
| idle | worker started | working | READ |
| complete, fail, cancel | worker started again | working | INFERRED |
| working | worker returns success | complete | READ |
| working | worker returns error | fail | READ |
| working | stop requested, worker unwinds | cancel | READ |

### Function events

A function event has `Event` (the function name), `Timestamp`, `state`, and these optional
members: `stage` (non-empty stage text), `lapse_ms` (running time in ms), `code` and `error`
(only at `fail`), `route` (ancestor names, only when routing is enabled), plus
function-specific members. READ. Full rules are in [events/families.md](events/families.md).

R1. A function event is sent when the worker starts (`working`) and when it ends. No periodic
event is guaranteed in between. Start or end sends can be suppressed by framework flags. READ. A
client MUST NOT treat a missing end event as proof that the function is still working; it SHOULD
re-read state with `iscope_get_app_state` after reconnect. INFERRED.

R2. The same state record appears inside [`iscope_get_app_state`](../../docs/control/methods/iscope_get_app_state.md)
without `Event` and `Timestamp`. READ.

R3. Some older workers send simple state events instead (`start`, `complete`, `fail`, with
`code`/`error` only when the code is > 0). These are a different serializer. READ. A client MUST
accept both state vocabularies for the event names marked "S" below.

### Known function and event names

| Name | Started by | Extra members | Label |
|---|---|---|---|
| [`ViewPlan`](../../docs/control/events/ViewPlan.md), [`Target`](../../docs/control/events/Target.md) | `set_view_plan` | see [plan-scheduling.md](plan-scheduling.md) | READ |
| [`ScanSun`](../../docs/control/events/ScanSun.md) | `start_scan_planet` | none (function family only) | READ |
| `PlanetStack` | `start_planet_stack` | `percent`, `input_thn`, `output_file` | READ |
| `ObjectTrack` | object tracker | `x`, `y`, `width`, `height` | READ |
| `RTSP` | stream worker | `roi_index`, `roi_scale`, `port`, `route` | READ |
| `AviRecord` | `start_record_avi` (also S) | [AVI recording](#avi-recording) | READ |
| `AviRtmp` | `start_avi_rtmp` (S) | none | READ |
| [`Demonstrate`](../../docs/control/events/Demonstrate.md) | `start_demonstrate` | none established | Emitter and payload READ; event name INFERRED |
| [`AIProcess`](../../docs/control/events/AIProcess.md) | `start_ai_process` | `ori_name`, `dst_name` at complete | READ; see [AI processing](solving-and-annotation.md#ai-processing) |
| [`CreateHPC`](../../docs/control/events/CreateHPC.md) | `start_create_hpc` | `hpc_num` | Emitter and payload READ; event name and the link to `start_create_hpc` INFERRED |
| [`GoPixel`](../../docs/control/events/GoPixel.md) | `start_func` `GoPixel` | `cur_pix` `[x, y]` | Emitter and payload READ; event name INFERRED (the request name need not equal the event name) |

### Function control methods

R4. [`stop_func`](../../docs/control/methods/stop_func.md) takes `{name}`, a bare string, or
`[name]`; a missing or non-string name gives 105. READ. Any string is accepted. The device stops a
matching local function and then relays the request to the wide process. The reply is 0 even
when no function matched. READ. A client MUST NOT read success as "a function was stopped". The
app sends names `ViewPlan` and `AIProcess`. READ.

R5. If the relay fails locally, the reply is replaced by `{error, code, id}`; `code` is 300 when
the relay context is missing. That reply lacks `method`, `jsonrpc` and `Timestamp`. READ. A client
MUST match such a reply by `id` alone.

R6. `stop_func` can block until the worker exits. No timeout is set. READ.

R7. [`is_func_work`](../../docs/control/methods/is_func_work.md) takes `{keys: [string, ...]}` and
returns one boolean: true if any named function is in state `working`. Non-string elements are
skipped. An empty array gives false. Missing `keys` or non-object params gives 207. READ.

R8. [`start_func`](../../docs/control/methods/start_func.md) accepts only `{name: "GoPixel", x, y}`
(exact, case-sensitive). Any other name gives 100. `x` and `y` are integer display-pixel
coordinates (INFERRED). The device converts them to sensor pixels, then starts a worker that
centres the mount on that pixel. READ.

R9. If `x` or `y` is missing or not an integer, the reply carries neither `result` nor `error`.
READ. A client MUST always send both as integers.

R10. `start_func` first checks mount occupancy and can return 203 `equipment is moving`. Other
errors: 209 (bad crop or wrong camera), 268 (already centring), 212. READ. Reply 0 means the
worker started, not that the mount arrived.

## Sun, Moon and planet modes

### Scan

R11. [`start_scan_planet`](../../docs/control/methods/start_scan_planet.md) takes no params. It
needs view mode 2, 3 or 4 and a free function slot; otherwise it returns 524 `function conflict`.
READ. The relay check runs with relaying disabled in firmware 9.75, so the request is not forwarded; 203 is returned when the mount is occupied and 300 on a missing context (firmware 9.31 call form not diffed).
212 on thread failure. READ. The app calls it "start scan Sun or Moon". READ.

R12. The scan worker is the `ScanSun` function. It searches with the mount using child goto
operations. READ. Its state changes are sent as [`ScanSun`](../../docs/control/events/ScanSun.md)
function events, named after the function. READ. The handler itself emits no event. The events
carry only the function-family members. READ.

R13. [`stop_lock_sun`](../../docs/control/methods/stop_lock_sun.md) takes no params, stops the
lock-sun worker and the scan, and always returns 0. It can block until both exit. READ.

### Sync and pointing

R14. [`scope_sync_planet`](../../docs/control/methods/scope_sync_planet.md) takes no params.
It works only in view mode 2 (moon) or 3 (sun); otherwise 300. READ. It computes the body's
position, converts RA from degrees to hours (INFERRED from division by 15), and sends a mount sync
with a 10 s wait. Errors 241 `send request to guider error` and 502 `mount sync failed`. READ. The app
calls it "sync planet". READ.

R15. [`get_go_cmd`](../../docs/control/methods/get_go_cmd.md) takes no params. It starts the wide
camera stream, finds the Sun or Moon in one frame, and returns a string of motor commands joined by
`;` (with a trailing `;`). It does not execute them. READ. It runs only on supported models with
the expected camera selected; other models return an error string. READ. Each command has the
form `:Mp±NNNNNN:±NNNNNN#`: two signed offsets in arcseconds, zero-padded to six digits. READ.
The offsets are consecutive steps, each relative to the previous point. INFERRED. On S30 Plus-class
units the `ScanSun` worker fetches this list from the peer unit after its first goto and sends each
command to the mount. READ. Because it starts and stops a camera stream, a client MUST NOT call it
as a passive query.

The handler reads the two fields of each detected point in a fixed order (the first struct member,
then the second) and substitutes them into the command string in that same order, unchanged. READ.
Which mount axis each field drives is unresolved: that mapping is made by the mount controller's
own command interpreter, a separate microcontroller whose firmware is not in this evidence set, so
no further static reading of the imager or guider binaries can settle it. unresolved (mount
controller firmware; needs a device test).

### Planet stacking

See [Stacking: Planet stack](stacking.md#planet-stack) for parameters, events and lifecycle.

## Object tracking

R20. [`start_track_object`](../../docs/control/methods/start_track_object.md) takes `{x, y, width,
height}`, all integers and all required (104). The values are display coordinates and are converted
to sensor coordinates. Width or height <= 0 is replaced by the camera subframe. READ. Firmware 9.75
(64-bit): an optional boolean `is_manual_selection` is read (106 if present and not a boolean;
default true), the coordinates are converted with the show-to-sensor conversion instead of the 9.31
conversion, and when `is_manual_selection` is false a rectangle-correction step runs first (a change
is logged). READ. If smart follow is running, the rectangle is submitted to smart follow: success
replies 0, and the error code on failure comes from the thread's error state and is unresolved.
Otherwise object tracking starts and a failure returns the thread's error code. READ (routing). The
32-bit build has no `is_manual_selection` string while the smart-follow submit symbol is present;
its handler probably differs (unresolved).

R21. Preconditions: scenery mode (view mode 1) or the wide camera; the RTSP stream running; a
tracker available; RTMP not running. Errors: 300, 268, 203, 212. READ (firmware 9.31). Firmware
9.75: the RTMP condition is gone; the handler first tests whether smart follow or object tracking
already runs, then calls the full relay and occupancy check. READ. When the dual-camera main-process
flag is set and the "slave" flag is clear, the handler first asks the other process with
`is_func_work` whether `SmartFollow` and `ObjectTrack` work (10000 ms timeout each); if both do, the
relay is skipped. READ (64-bit firmware 9.75). Shared gating, occupancy checks, caller types and
relay-only rules are in [session dispatch
R31a](session-handshake/relay-routing.md#second-camera-relay-routing). The relay-only form replaces
the old wide-camera, view-mode and relay test in `iscope_match_target_name`,
`iscope_accept_target_name`, `stop_record_avi`, `start_ai_process`, `check_ai_process` and
`get_annotate_result`; it runs no occupancy probe, so 203 and 524 are not newly reachable there.
READ. Whether `start_auto_goto` and `start_solve` use it is not confirmed. The planet-stack
functions and the AVI-record-state formatter differ from 9.31 but were not examined (unresolved).

R22. The tracker reports through [`ObjectTrack`](../../docs/control/events/ObjectTrack.md)
function events with the tracked rectangle `x`, `y`, `width`, `height` (pixels, INFERRED). READ.
The handler itself emits nothing; that `start_track_object` triggers these events is INFERRED.

## Demonstration mode

See [Maintenance: Demonstration mode and sound](maintenance.md#demonstration-mode-and-sound).

## AVI recording

See [Video: AVI and MP4 recording](../media/video.md#avi-and-mp4-recording).

## Streaming and AVI playback

See [Video: Stream control from 4700](../media/video.md#stream-control-from-4700) and [AVI playback into the stream](../media/video.md#avi-playback-into-the-stream).

## Open questions

- Recording format and timelapse questions: see [Video open questions](../media/video.md#open-questions).
- Which mount axis each `get_go_cmd` offset drives (R15): the mapping is made by the mount
  controller's own firmware, not present in this evidence set; needs a device test.
- Bounded latency of every blocking stop.

## Appendix: How to validate on a live device (non-normative)

1. `is_func_work {keys:["AviRecord","ViewPlan"]}` while idle should give false.
2. In scenery mode with a stream, `start_record_avi {}` then `stop_record_avi`; watch `AviRecord`
   events for `file_saved`.
3. `start_avi_rtmp {name:"<a recorded file>"}` with a wrong name; expect reply 0 and then
   `AviRtmp fail` with 258.
4. `stop_func {name:"NoSuchFunc"}` should return 0.
