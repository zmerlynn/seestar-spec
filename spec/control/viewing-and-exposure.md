# Viewing and exposure

Scope: the control-service workflow for opening the main camera, starting and stopping a view
mode, the view stages that run inside it, plain exposures, and camera/ISP settings. It sits
above the JSON-RPC envelope and event delivery rules ([session-handshake.md](session-handshake.md),
[events/envelope.md](events/envelope.md), [events/families.md](events/families.md)) and below the
work that runs inside a view: [stacking.md](stacking.md), [focus-and-filter.md](focus-and-filter.md),
[solving-and-annotation.md](solving-and-annotation.md), [calibration-frames.md](calibration-frames.md)
and [plan-scheduling.md](plan-scheduling.md). Per-method detail stays in the catalog cards.

App names: the home-screen modes “Stargazing” (`mode:star`), “Scenery” (`mode:scenery`) and “Milky
Way” (the wide-camera star view, not a separate mode) all start a view here. “Continuous Capture” is
`stack.capt_type:cont_capt`. “4K” and “Telephoto resolution” set `wide_4k` and `main_8k`; which
preset sets `main_8k` is INFERRED. Names are the English strings of iOS app 3.4.0; links are READ
(app call sites) unless marked.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients. Sentences saying what "the device" does are descriptions.

Labels follow `CONVENTIONS.md` and [plan-scheduling.md: Conventions](plan-scheduling.md#conventions): **READ**
(firmware 9.31 static analysis), **OBSERVED** (seen on a device; no session is matched to 9.31
exactly, so treat as hints), **INFERRED**, **unresolved**. READ claims are for the 64-bit
imager build; the 32-bit build is "probable" unless stated. Integers are signed 32-bit.

Shared rules used by every chapter in this group (READ):

- Success reply: `{method, result, code:0, id}`. Error reply: a top-level `error` string and a
  nonzero `code`, no `result`. A failure that left code 0 is reported as 207. Receivers MUST NOT
  require `jsonrpc` or `Timestamp` in replies.
- "Started" replies (`result` 0 from a `start_*` method) mean a worker thread was launched. They
  never mean the work completed. Outcome arrives as events or through a getter.
- Function events (family F, see [events/families.md](events/families.md)) carry
  `state` in `idle | working | complete | fail | cancel`, optional `stage`, `lapse_ms`, optional
  `route`, and `error`/`code` on `fail`. A stop that clears the continuation flag ends the
  function with `cancel` (internal code 253).
- Events go to every connected control socket. There is no ordering guarantee between a reply
  and the events caused by the same request (READ; see [events/envelope.md](events/envelope.md#ordering)).

Basis: static analysis of firmware 9.31 / app 3.3.2, with firmware 9.75 / app 3.4.0 deltas tagged "firmware 9.75" (64-bit build unless stated).

## Objects and state

The device holds one main camera, a "page" (app page; 0 is the normal imaging page, 1 the
focus/video page), an exposure mode, a view mode and a function tree. READ.

| Object | Values | Set by |
|---|---|---|
| Camera state | `close`, `idle` | `open_camera`, `close_camera` |
| View mode | star, scenery, moon, sun, planet, solar_sys, none | `iscope_start_view`, `iscope_stop_view` |
| View stage (star mode) | 0 idle, 1 AutoFocus, 2 AutoGoto, 3 Stack, 4 Sleep, 5 CheckPhotoMetry | stage starters |
| Page | 0 preview, 1 focus, 2 autosave, 3 pa (polar alignment), 4 stack, 5 rtmp, 6 plan | `open_camera`, `start_single_expose`, stage starters, `set_page` |
| Exposure mode | 0 single, others continuous, sequence; 3 refused by `start_exposure` | page changes and settings |

The numeric mapping of view-mode names to ids is not stated here; the card for
[`iscope_start_view`](../../docs/control/methods/iscope_start_view.md) gives the parser
rules (accepted ids 0..5). The stage and page values above are the complete sets in this
firmware. READ. [`set_page`](../../docs/control/methods/set_page.md) takes the page name as a
string; a non-string gives 105 and an unknown name gives 109. READ. Clients MUST accept any of these values
in events and state.

The `View` function is the root of the view subtree. Its children (Stack, AutoFocus,
AutoGoto, PlateSolve, ...) appear as dynamic keys in
[`get_view_state`](../../docs/control/methods/get_view_state.md) and in
[`iscope_get_app_state`](../../docs/control/methods/iscope_get_app_state.md). READ. Function names
compiled into the imager are View, Initialise, AutoGoto, AutoFocus, Stack, AutoExp, Exposure,
PlateSolve, Annotate, CheckPhotoMetry, Sleep, ScopeGoto, GoPixel, FocuserMove, SaveImage,
ObjectTrack, AIProcess, PlanetStack, BatchStack, ScanSun, AviRtmp, RTSP, 3PPA, MountUpdate,
CalibGSensor, Demonstrate, ViewPlan and Target. READ. Which of them appear under View depends
on the active mode. unresolved. OBSERVED (2026-10-16): on an idle device `get_view_state` listed
`View`, `Stack` and `Exposure`, all in state `cancel`, so `Exposure` can appear under `View`. In `get_view_state` the result is the View function's detail
followed by its live children, nested by name; each node carries `state`, `code`, `error`,
`lapse_ms` and `stage` plus function-specific members. READ. Clients MUST ignore child names and
node members they do not recognise.

## Camera lifecycle

```
 client                                device
   | get_connected_cameras  ------------>|  list [{name,id,path}]
   | open_camera [0]        ------------>|  open, restore settings, page := 0
   |<---------------------- result 0     |
   |<---------------------- CameraStateChange (Event, Timestamp only)
   | ... imaging ...                     |
   | close_camera           ------------>|  stop ViewPlan/stack, stop view, stop exposure
   |<---------------------- result 0     |
   |<---------------------- CameraStateChange
```

R1. A client MUST open the camera before any exposure, view-stage or camera-setting call.
Most of those return 318 (`device not connected`) on a closed camera. READ.

R2. [`open_camera`](../../docs/control/methods/open_camera.md) takes an integer ordinal
(default 0). It returns 204 for an ordinal out of range, 109 for a wrong type and 300 when a
camera is already open. READ. The device already attempts to open the camera during boot
initialisation, so a client's first `open_camera` can return 300. READ. A client SHOULD check
[`get_camera_state`](../../docs/control/methods/get_camera_state.md) first and treat `idle`
as "already open". `open_camera` has no ViewPlan guard; when it opens the camera it applies the
stored auto-cooler setting and, conditionally, heater setup. READ. An open camera is not
capturing: open is a logical state distinct from active capture, and re-opening is not a warm-up
step (INFERRED).

R3. [`close_camera`](../../docs/control/methods/close_camera.md) is idempotent: it succeeds on
an already-closed camera. Before freeing buffers it stops any ViewPlan, the live stack, the
view (a full view stop) and the exposure (an exposure stop). READ. Closing the camera
therefore ends every imaging workflow in this chapter group.

[`CameraStateChange`](../../docs/control/events/CameraStateChange.md) is an Event/Timestamp-only
notification sent after a successful `open_camera` or `close_camera`. It carries no state; a
client SHOULD treat it as a hint to re-read `get_camera_state`. READ.

## Starting and stopping a view

[`iscope_start_view`](../../docs/control/methods/iscope_start_view.md) selects a view mode
and launches the view worker. [`iscope_stop_view`](../../docs/control/methods/iscope_stop_view.md)
stops the whole view or one named stage.

```
 client                                     device
   | iscope_start_view {mode:"star",...} --->|  536? 107/105/102/204/209? 524? 318?
   |<------------------------- result 0      |  worker launched
   |<------------------------- View  state=working (mode, target_name, ...)
   |<------------------------- child function events (AutoGoto, Stack, ...)
   | iscope_stop_view {stage:"Stack"} ------>|  stop one stage
   |<------------------------- result 0      |
   |<------------------------- Stack state=cancel
   | iscope_stop_view (no params) ---------->|  full stop: mode := none
   |<------------------------- result 0      |
   |<------------------------- View  (detail resent, mode none)
```

R4. `params` MUST be an object with a string `mode`. Optional members: `target_name`,
`target_ra_dec` (two numbers: RA in decimal hours, then Dec in degrees; coordinates of date,
INFERRED, so a client SHOULD precess J2000 positions first), `lp_filter`, `target_type` (solar_sys
only), `mosaic`, `selected_cam` (View or SecondView). READ. The `mosaic` members and their effect at
capture are in [mosaic.md](mosaic.md). In firmware 9.75 the view starter also saves the star filter position, and the view stop differs. READ.

Firmware 9.75, 64-bit and 32-bit builds add optional `goto_capt_type` and `goto_capture_settings`. `goto_capt_type` is a string (105 otherwise) selecting only stack capture here; its name comparison is ASCII case-insensitive, and other capture types or unknown names give 209. `goto_capture_settings` is an object (107 otherwise) containing integer `stack_exp_ms` (104 when missing or non-integer). The decoded signed 32-bit exposure is accepted only when positive and accompanied by explicit stack capture selection, otherwise 209. `stack_exp_ms` is nested inside that object. READ. No additional exposure upper-bound comparison occurs in the inspected handler; this is not an arbitrary-precision wire-integer guarantee.

On the main-camera goto stage outside ViewPlan, with view parameters available, these fields can switch capture to stack and update its exposure through ordinary stack-setting application before goto. READ. Exposure normalization can change the effective value; parser acceptance alone does not establish the final exposure. Firmware 9.31's inspected builds do not read these fields. Full exposure-normalization and other build-specific lifecycle behavior remain outside this finding. A mosaic view has no completion of its own and runs until stopped. `lp_filter` is passed to the target's goto; it moves the wheel to the LP
slot only inside a ViewPlan or with `stack.auto_lenhance` on, and the view start itself never moves
the wheel ([focus-and-filter
R22d](focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves)). READ.

R5. The ViewPlan guard runs first: while a ViewPlan worker runs, both start and stop return
536 before any parameter is parsed. READ. A client MUST stop the plan
([plan-scheduling.md](plan-scheduling.md)) before taking manual control of the view.

R6. A success reply means the worker was launched, not that the view is ready. A client MUST
wait for the [`View`](../../docs/control/events/View.md) event (or poll `get_view_state`) before relying on view state. READ.

R7. Starting a view stops the previous view worker and exposure, and may open and move the
focuser. READ. A client MUST NOT assume a running stack or goto survives a new
`iscope_start_view`.

R8. On wide-camera models the start, stop and several stage starters may be relayed to the
second camera process. The reply is then the relayed reply. Relay failures give 300 or a
copied peer code; each relay waits up to 10000 ms. READ. Wide-camera view state is reported
as [`SecondView`](../../docs/control/events/SecondView.md), forwarded from the wide process.

R9. `iscope_stop_view` without a usable `stage` string performs a full stop: view mode returns
to none, binary image sending stops and view workers stop. With a string `stage`, only that
named function is stopped; an unknown or idle name is not an error. READ. Names the app
sends: 3PPA, AutoExp, DarkLibrary, AutoGoto, Initialise, ObjectTrack, ScanSun, Stack
(app-sent names, not a firmware enum).

R10. The 64-bit build returns 210 for `stage:"AutoExp"` on the main process when the current
mode is star without wide support. The 32-bit build lacks that branch. READ.

R11. A full stop (a full view stop with a non-none mode) resends the `View` detail without a
new F state. A client MUST NOT treat a repeated `View` event with the same `state` as a
duplicate: the payload fields can differ. READ, INFERRED consequence.

### View stages started directly

These starters stop the current view, set view mode 0 and page 0, clear the subframe and start
the View worker on one stage. If the same stage already runs they return success early
(before the camera check). Otherwise a closed camera gives 318 and a thread failure 212. READ.

| Starter | Stage | Chapter |
|---|---|---|
| [`iscope_start_stack`](../../docs/control/methods/iscope_start_stack.md), [`start_stack`](../../docs/control/methods/start_stack.md) | 3 Stack | [stacking.md](stacking.md) |
| [`start_auto_focuse`](../../docs/control/methods/start_auto_focuse.md) (one branch) | 1 | [focus-and-filter.md](focus-and-filter.md) |
| [`start_view_star_sleep`](../../docs/control/methods/start_view_star_sleep.md) | 4 Sleep | this chapter |
| [`check_photometry`](../../docs/control/methods/check_photometry.md) | 5 | [solving-and-annotation.md](solving-and-annotation.md) |

R12. Because each starter stops the current view, starting one stage interrupts any other
stage. A client SHOULD check `get_view_state` before starting a stage it does not own.

### View state transitions

| From | Trigger | To | Event |
|---|---|---|---|
| none | `iscope_start_view` accepted | mode = requested, View working | `View` working |
| any mode | `iscope_start_view` (new mode) | previous worker stopped, new mode | `View` (new detail) |
| mode set | stage starter | star mode 0, stage n | `View`, child F event |
| mode set | `iscope_stop_view` with stage | stage stopped, mode kept | child `cancel` (INFERRED) |
| mode set | `iscope_stop_view` full / `close_camera` | none | `View` detail resent |

On a full stop the View function ends with `cancel`, then its detail is resent with mode none.
READ (the stop mechanism) / INFERRED (applied to View). In general a function stopped from
outside ends with `cancel`; one that ends by itself ends `complete` or `fail` with its code.
READ.

## Exposures

Three entry points start capture. All run asynchronously.

| Method | Effect | Notes |
|---|---|---|
| [`start_exposure`](../../docs/control/methods/start_exposure.md) | single, continuous or sequence, by current exposure mode | optional `type`, `keep_autosave_dev` |
| [`start_single_expose`](../../docs/control/methods/start_single_expose.md) | page := 0 and exposure mode 0, then `start_exposure` logic | page changes even on 318 |
| [`stop_exposure`](../../docs/control/methods/stop_exposure.md) | abort | `wait` defaults to true |

R13. `start_exposure` checks, in order: 210 while three-point polar alignment (3PPA) runs; 106,
105 or 209 for malformed `keep_autosave_dev` or `type`; then 318 (camera closed), 206 (capture
already active), 524 (planet stack active), 102 (exposure mode 3), 208 (sequence disk-space
check fails). READ. `type` (light, dark, bias, flat; case-insensitive) is read only in
exposure mode 0, and it changes the frame selection before any later failure (no rollback).

R14. `start_single_expose` has no 3PPA check, unlike `start_exposure`. READ. A client SHOULD
NOT call it while polar alignment runs.

R15. `stop_exposure` sets the capture error to 253 (`aborted`) and returns 0 on every ordinary
path, including when no exposure runs. With `wait` true (default) it joins the worker with no
bounded timeout, so the reply can be delayed indefinitely. READ. A client that must stay
responsive SHOULD send `{"wait": false}` and watch events.

R16. [`can_liveview`](../../docs/control/methods/can_liveview.md) returns a boolean (false with
code 0 when the camera is closed). [`can_abort_expose`](../../docs/control/methods/can_abort_expose.md)
returns true, or 318. READ.

### Exposure events

[`Exposure`](../../docs/control/events/Exposure.md) has two producers. A client MUST accept
both shapes.

| Producer | States | Members |
|---|---|---|
| Legacy (sent only when the exposure's event flag is set) | `start`, `downloading`, `complete`, `fail` | `page`, optional `tag`; `start` adds `exp_us`, `gain`; `fail` adds `error`, `code` |
| Function (F) | F states | F members plus `exp_ms` (number, milliseconds), `port` (JSON event-server port, not the image port) |

READ. OBSERVED (2026-10-12): both shapes on the wire; a legacy `fail` with code 514; an
exposure cycle near 63 s in one session. Code 514 `interrupt` means a running operation
(stacking, auto-exposure, star finding, saving, or a view plan) was stopped by the device itself,
usually because the mode or page changed or another command superseded it. Only those application
workers produce 514; the camera layer never does. READ (producers), INFERRED (which internal stops
trigger it live). It does not indicate a camera or sensor fault: clients SHOULD NOT treat it as one,
and retrying after the conflicting action is the correct response. An exposure stopped by `stop_exposure` reports 253, and 238 means the capture
retries ran out. READ.

Continuous capture reports [`ContinuousExposure`](../../docs/control/events/ContinuousExposure.md)
(F plus `fps`). Auto exposure reports [`AutoExp`](../../docs/control/events/AutoExp.md) (F;
`exp_us` added only at `complete` with a positive saved exposure). READ.

## Camera and ISP settings

| Area | Methods | Rules |
|---|---|---|
| Info | [`get_camera_info`](../../docs/control/methods/get_camera_info.md) | chip size, bins, pixel size, unity gain, cooler, colour, debayer pattern; 318 |
| Bin | [`set_camera_bin`](../../docs/control/methods/set_camera_bin.md), [`get_camera_bin`](../../docs/control/methods/get_camera_bin.md) | page 0: value MUST be in `bins` (210); page 1: 1..max bin (204) |
| Exposure + bin | [`set_camera_exp_and_bin`](../../docs/control/methods/set_camera_exp_and_bin.md), [`get_camera_exp_and_bin`](../../docs/control/methods/get_camera_exp_and_bin.md) | object; applied in wire order, no rollback; `exposure` is an integer in microseconds (10 s = 10000000) |
| Controls | [`get_controls`](../../docs/control/methods/get_controls.md), [`get_control_value`](../../docs/control/methods/get_control_value.md), [`set_control_value`](../../docs/control/methods/set_control_value.md) | name case-insensitive; limits from `get_controls` |
| Bit depth | [`set_camera_16bit`](../../docs/control/methods/set_camera_16bit.md), [`get_camera_16bit`](../../docs/control/methods/get_camera_16bit.md) | strict boolean; see R19 |
| Focal length | [`get_focal_length`](../../docs/control/methods/get_focal_length.md), [`set_focal_length`](../../docs/control/methods/set_focal_length.md) | millimetres (number); factory default 250; see R20 |
| Subframe | [`set_subframe`](../../docs/control/methods/set_subframe.md), [`get_subframe`](../../docs/control/methods/get_subframe.md) | page 1: video rectangle; else camera crop |
| ISP rate | [`set_isp_fps`](../../docs/control/methods/set_isp_fps.md) | 0..30 stored; outside normalised to 0, no error |
| Misc | [`get_gain_segment`](../../docs/control/methods/get_gain_segment.md), [`get_sensor_temperature`](../../docs/control/methods/get_sensor_temperature.md) | `[minimum gain, segment break, maximum gain]` (R17a); temperature from the IMU, not the sensor |

R17. The device keeps its own control table, built when the camera opens; it is not the camera
library's list. Each entry has an imager control id, a name taken from the imager's name table,
`min`, `max` and `read_only`; there is no default or current value. `get_controls` returns exactly
these entries. READ (64-bit build). The entries are:

| Id | Name | `min` | `max` | `read_only` | Present |
|---:|---|---:|---:|---|---|
| 0 | `Gain` | 0 | camera's maximum gain | false | always |
| 1 | `Exposure` | 30 | camera library's exposure maximum | false | always |
| 4 | `Temperature` | not set | not set | true | always |
| 5 | `CoolPowerPerc` | 0 | 100 | false | cooled cameras |
| 6 | `TargetTemp` | -40 | 30 | false | cooled cameras |
| 7 | `CoolerOn` | 0 | 1 | false | cooled cameras |
| 8 | `AntiDewHeater` | 0 | 1 | false | cooled cameras |
| 19 | `Red` | 0 | 100 | false | always |
| 20 | `Blue` | 0 | 100 | false | always |
| 22 | `FanHalfSpeed` | 0 | 255 | false | cooled cameras, 64-bit build only |
| 23 | `HPC` | 0 | 1 | false | always |
| 24 | `ISP_Gain` | 0 | as `Gain` | false | always |
| 25 | `ISP_Exposure` | 30 | 1000000 | false | always |

All READ (64-bit build), except: the `ISP_Gain` limits and the `Temperature` limits are left over
from the entry built before them, INFERRED; that the presence condition means "camera has a
cooler" is INFERRED; that the camera's maximum gain is the same value as the `max` of
[`get_gain_segment`](../../docs/control/methods/get_gain_segment.md) is INFERRED. The 32-bit build
uses the same table, fields and names, but has no `FanHalfSpeed` entry. READ (field layout and
strings), INFERRED (the resulting set).

The two camera-supplied limits differ by build:

- 32-bit build: the `Exposure` entry is not camera-supplied. The imager sets it to a fixed
  30 .. 2000000000, so the `max` in the table above is 2000000000 on this build. READ (32-bit,
  firmware 9.31 and 9.75). The `Gain` maximum comes from the camera library compiled into the
  imager, which sets 400 for the primary camera on every model branch, and 600 for the secondary
  (wide) camera on the S30 Pro and S50 Pro model branches. READ (32-bit, 9.31 and 9.75). Which
  physical sensor each branch drives is not established from the code; the package's per-model
  sensor tuning files suggest associations, INFERRED.
- 64-bit build: both limits come from the camera driver when the camera opens. The shipped camera
  SDK reads them from the driver and does not hold them as constants, so their per-camera values
  are unresolved. This holds for every 64-bit model package in firmware 9.75 (S30 Plus, S30 Pro,
  S50 Pro, S80). READ (source of the values), unresolved (the values). The S80 package also ships
  a second camera library whose two sensor classes declare gain 0..600 and exposure maxima of
  1000000 and 2000000000 microseconds, but neither the 64-bit imager nor its camera SDK links to
  that library, so a client SHOULD NOT assume those values are what `get_controls` reports. READ
  (firmware 9.75).

A client SHOULD read limits from `get_controls` rather than assume static ranges.
This control-table build, its ids and names, and the `get_controls`/`set_control_value`/
`get_control_value` dispatch described in R17-R17d are confirmed unchanged in firmware 9.75, both
the 64-bit and 32-bit builds (identical instruction counts; only relocation differences). READ.

The imager's own name table (used for the case-insensitive matching in R17d) is wider than the
13 entries `get_controls` exposes: it spans ids 0..25 (26 real entries — the ones listed above
plus the library-only names of R17c). A static scan of the table also reads one further row past
id 25; that row is a scan/parsing artifact, not a 27th control id, and does not correspond to any
real control. READ. Confirmed unchanged in firmware 9.75, both builds.

R17a. `get_gain_segment` returns `[0, 131, max]`: the first two are fixed in this firmware and
`max` is the camera's maximum for its first control. READ. That `max` is the maximum gain is
INFERRED. 318 when the camera is closed. READ.

The segment break 131 is a constant in the imager, identical in both builds and in firmware 9.31
and 9.75, and is not computed from the camera library's conversion-gain settings. READ. Those
settings put the switch elsewhere: the 32-bit build's compiled-in camera library requests high
conversion gain when the requested gain is at least 200 on most model branches and at least 80
on the S50 branch (and subtracts the branch's offset from the gain it then programs), while the
64-bit camera SDK computes its switch point from values the driver supplies. READ (firmware 9.31
and 9.75). Whether 131 marks a high-conversion-gain switch on any camera is therefore unresolved,
and a client SHOULD NOT treat it as one.

R17b. Control values are integers in fixed units. READ (camera library) unless marked.

| Control | Unit |
|---|---|
| Exposure (id 1) | microseconds (2000000 is 2 s). INFERRED (from the library's conversion of the value to sensor lines) |
| Gain (id 0) | tenths of a dB on sensors with multiplicative gain; a raw analogue-gain value on other sensors |
| Offset | raw sensor black level |
| Temperature | tenths of a °C, read-only |
| TargetTemp | °C, clamped to -40 .. 30 |
| Cooler power | percent |
| Cooler on | boolean |
| Red, Blue (white balance) | gain where 100 is unity; affects only pixel format 3 (R19) |
| Anti-dew heater, fan, power LED, test pattern | passed unchanged to the peripheral |

On camera open the device sets exposure to 500000 (0.5 s, unit INFERRED as above) and gain
to 0. READ.

R17c. The camera library's own control-id enum (`ASI_CAM_CONTROL_TYPE_E`) is fixed by the vendor
SDK and is a different id space from the imager's own 0..25 name-table ids of R17:

| Camera-library id | Name |
|---:|---|
| 0 | `Gain` |
| 1 | `Exposure` |
| 2 | `Gamma` |
| 3 | `WB_R` |
| 4 | `WB_B` |
| 5 | `Offset` |
| 6 | `BandwidthOverload` |
| 7 | `Overclock` |
| 8 | `Temperature` |
| 9 | `Flip` |
| 10 | `AutoMaxGain` |
| 11 | `AutoMaxExp` |
| 12 | `AutoTargetBrightness` |
| 13 | `HardwareBin` |
| 14 | `HighSpeedMode` |
| 15 | `CoolerPowerPerc` |
| 16 | `TargetTemp` |
| 17 | `CoolerOn` |
| 18 | `MonoBin` |
| 19 | `FanOn` |
| 20 | `PatternAdjust` |
| 21 | `AntiDewHeater` |
| 22 | `FanAdjust` |
| 23 | `PwrLedBright` |
| 24 | `UsbHubReset` |

READ (type information carried in the 64-bit camera library; the 32-bit backend links the same
vendor SDK headers, so the ids are the same by construction, INFERRED). Ids 0, 1, 3, 4, 15, 16 and
17 are the ones the device's own table reaches, through the mapping in R17e; id 22 is reached only
indirectly, as the extra call R17e describes when `CoolerOn` is set on. `Gamma`,
`BandwidthOverload`, `Overclock`, `Flip`, the three auto-exposure ids, `HardwareBin`,
`HighSpeedMode`, `MonoBin`, `FanOn` and `UsbHubReset` have no entry in the device's own table, and
inside the library, setting them succeeds with no effect. READ (camera library). None of them is
reachable through `set_control_value`, which rejects their names with 210 (R17d), except
`MonoBin`, which the device stores as a setting instead. READ. `Offset`, the library's own
`Temperature`, `PatternAdjust` and the library's own `AntiDewHeater` (distinct from the device's
own `AntiDewHeater` entry, which R17b says is passed straight to the peripheral rather than
through this library control) likewise have no entry in the device's own table and so are equally
unreachable through `set_control_value`. Firmware 9.31 and 9.75, 64-bit libraries (READ): the direct MIPI SDK handles library `Offset` by requesting the kernel black-level control, library `Temperature` as a success no-op, `PatternAdjust` by requesting the kernel test-pattern control, and library `AntiDewHeater` through the heater peripheral when the camera has the relevant cooling capability. In the separate camera library, `Offset` dispatches to the selected sensor setter; the S585 Seestar setter clamps black level to 0..200 and requests sensor-register writes. Library `Temperature` is a success no-op, S585 Seestar `PatternAdjust` uses the inherited success no-op, and library `AntiDewHeater` is handled by the cooler class. Firmware 9.75, 64-bit library (READ): the S585 black-level path additionally requests an auxiliary controller command. These are direct library controls, distinct from the device's control-id mapping and its same-named Temperature/heater handling. Kernel/controller acceptance and physical effects remain unresolved.

R17d. Name matching. `get_control_value` and `set_control_value` match the name against the
imager's name table without regard to case. READ. `set_control_value` accepts `Gain`, `Exposure`,
`Red`, `Blue` and `MonoBin` specially (gain and exposure also store the active page's setting;
`MonoBin` only stores the mono-bin setting, although it has no table entry), and otherwise any
name whose id is in the table. A name that is unknown or whose id is not in the table gives 210;
a closed or absent camera gives 318 before the name is even looked up. READ. The setter makes
**no** range check against `min` and `max`; out-of-range handling is left
to the camera backend. READ (no check in the imager). Firmware 9.31 and 9.75, 64-bit and 32-bit builds (READ): the imager does not validate requested values against the min/max reported by `get_controls`. Backend behavior varies. The 64-bit MIPI SDK has no general capability-range clamp; target temperature has a -40..30 °C clamp, and cooler power has separate state-dependent bounds. The separate 64-bit camera library clamps supported controls to their capability min/max before dispatch. The 32-bit compiled gain setters check a stored maximum, and the exposure setter checks an unsigned converted result against 2000000000 before its remaining camera-state/kernel path. These checks do not define one acceptance rule for every control or extreme input. Further driver validation and physical effects remain unresolved. Setting
`Temperature` returns success and changes nothing. READ. `ISP_Gain` returns success without a
camera update. READ. This dispatch (no range check; 210 on a name/id miss; 318 on a closed
camera) is confirmed unchanged in firmware 9.75, both builds.

R17e. `set_control_value` maps some of the device's own control ids (the `Id` column above) to a
separate camera-library control id before calling into the library:

| Device id | Name | Camera-library control id |
|---:|---|---:|
| 0 | `Gain` | 0 |
| 1 | `Exposure` | 1 |
| 19 | `Red` | 3 |
| 20 | `Blue` | 4 |
| 5 | `CoolPowerPerc` | 15 |
| 6 | `TargetTemp` | 16 |
| 7 | `CoolerOn` | 17 |

READ. These two id spaces are distinct from each other and from the 0..25 imager name-table ids
of R17/R17c. `ISP_Exposure` (id 25) scales the value by 1/1,000,000 before the equivalent
library call (already noted in R17b's unit table); `ISP_Gain` (id 24) only logs the value and
makes no library call (R17d); `HPC` (id 23) calls the library's hot-pixel-correction control.
Camera-library control id 22 is fan speed. Firmware 9.31 and 9.75, 64-bit build (READ): setting `CoolerOn` to exactly 1 additionally requests fan value 255 when the camera's per-model half-speed preference is false, or 127 when it is true. The preference is read when the camera opens and defaults to false. A different positive value does not make this extra fan request; a nonpositive value additionally requests zero cooler power. The corresponding extra fan request is absent from the 32-bit integer setter in both firmware versions (READ). The saved preference on a particular device and the physical fan-speed effect of these backend values remain unresolved. The rest of R17e is confirmed unchanged in firmware 9.75, both builds. READ.

R18. Multi-field setters (`set_camera_exp_and_bin`, `set_control_value` for TargetTemp) apply
changes before a later failure and do not roll back. After any error a client SHOULD re-read
the value. READ.

R19. `set_camera_16bit` accepts only `true`, which selects pixel-format value 3; `false`
returns 210. `get_camera_16bit` reports true only for a two-bytes-per-pixel format (value 2), so
it reports false after `set_camera_16bit true`. READ (both builds). The parameter MUST be a JSON boolean
(integers are rejected); any other type gives 106. READ (both builds). Pixel format 1 is
8-bit raw and 2 is 16-bit raw (10- or 12-bit samples widened, with hot-pixel correction). Pixel
format 3 is an 8-bit Bayer mosaic produced by subtracting the black level, applying the red/blue
white-balance gains (R17b) and scaling to 8 bits with clipping at 255; it is not debayered and has
one byte per pixel. Cropped capture supports only format 3. READ (64-bit camera library),
INFERRED (32-bit camera backend). So `true` does not select 16-bit capture and a client MUST NOT
infer bit depth from it.

R19a. `set_camera_16bit` and `get_camera_16bit` give 318 when no camera is open, and
`get_camera_16bit` gives 210 if the current format is neither 2 nor 3. READ (64-bit build); on
the 32-bit build the setter's 318 and the getter's 210 are also READ.

R20. Focal length is in millimetres; the device derives the plate scale in arcseconds per pixel
as pixel size (µm) × 206.265 × bin ÷ focal length. READ. `get_focal_length` returns a number on the 64-bit build and an integer on the 32-bit build;
`set_focal_length` stores the value on the 64-bit build and is an acknowledged no-op on the
32-bit build. READ (32-bit probable). Clients MUST accept both number forms.

R21. Bin, subframe and control changes made while a stack or view stage runs take effect on
later frames. The live-stack worker checks no size, bin or subframe; whether the stacking engine
rejects mismatched frames is unresolved.

R22. [`save_image`](../../docs/control/methods/save_image.md) saves the image already in
memory; it reads no params. It returns 210 in exposure mode 2 and 207 without a usable image
buffer; 213 (`image is already saved`) may carry a top-level `fullname`. Success acknowledges
the start of an asynchronous save, reported by
[`SaveImage`](../../docs/control/events/SaveImage.md) (states `start`, `complete`, and the
literal `save fail` with a space; some fail paths have no `code`). READ.

Firmware 9.75: the camera library (libASICamera2.so) changed (about 4.0 MB to 4.4 MB). Firmware 9.75, separate 64-bit camera library (READ): the S585 gain, black-level, exposure and output-format paths add auxiliary controller requests, and the shared cooler-fan path adds another request. These auxiliary requests have a transport-selection guard. The S585 Seestar gain/black-level clamps and exposure register-write order remain present from firmware 9.31 (READ). The cooler-power path also gains a separate mode-dependent choice between its retained conversion and direct integer-percentage handling (READ). These changes do not establish a change in RPC exposure units or a physical change on every sensor. Firmware 9.31 and 9.75, 64-bit imager (READ): the traced MIPI calls use the camera SDK, with the S80 SDK override selected by the package installer; the 32-bit imager uses compiled camera-control paths (READ). Additional runtime use of the separate library, complete applicability to other sensors, and effects inside the absent kernel/controller implementations remain unresolved. No change in the wire units of R17b was found. READ. The device-side control table, ids, names and dispatch
logic in R17-R17e (what `get_controls` returns, how `set_control_value`/`get_control_value` resolve
a name, the absence of a range check, and the 210/318 error paths) are confirmed unchanged in
firmware 9.75 on both the 64-bit and 32-bit builds (identical instruction counts; only relocation
differences). READ.

### Additional camera control rules

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`get_controls`](../../docs/control/methods/get_controls.md) returns
`[{name, min, max, read_only}]`. 318 when the camera is closed. READ.

[`set_control_value`](../../docs/control/methods/set_control_value.md) takes `{name, val}` or
`[name, val]`. `val` may be integer, boolean, real or string, as the control needs. Errors 105,
109 unknown control, 210 not supported, 318. There is no rollback on partial failure. READ. The
cooler target temperature is handled specially. READ.

[`get_control_value`](../../docs/control/methods/get_control_value.md) takes `{name, items}`
and returns `{name, type, value}` with `type` one of `number`, `text`, `radio`, plus `text`,
`items` and `value_wide` when present. Errors 107, 109, 318. READ. The app asks for
`temperature`. READ.

[`set_subframe`](../../docs/control/methods/set_subframe.md) takes `{width, height, x, y}`
(or `[object]`); `width` and `height` MUST be > 0. Errors 107, 209, 204 out of limit, 210, 318.
[`get_subframe`](../../docs/control/methods/get_subframe.md) returns the same four members. READ.

[`set_isp_fps`](../../docs/control/methods/set_isp_fps.md) takes a bare integer (or
`[integer]`); an object gives 104. Values 0..30 are kept; anything else becomes 0 and still
returns 0. READ. The value is the ISP output frame rate in frames per second; 0 selects the
camera's automatic frame rate. READ. The setter only stores the value; it takes effect the next
time the preview stream's frame rate is configured, and one view mode forces 30 regardless.
READ (override) / INFERRED (timing).

### Gain (firmware 9.75)

Firmware 9.75, 64-bit build (READ): `Gain`, `ISP_Gain` and the live-video setting `isp_gain` have different setting paths. `set_control_value` with name `Gain` requests camera control 0 for the locally open camera. The inspected imager path does not compare the requested value with `get_controls` bounds and has no running-stack check. Backend acceptance and the frame of physical application remain unresolved.

Firmware 9.75, 64-bit build (READ): The opened-camera descriptors report gain minimum zero and a maximum obtained from the camera capability data. `ISP_Gain` inherits those bounds. These descriptors and `get_gain_segment` do not supply a physical gain step or a default gain. Per-model and per-port 64-bit maxima, physical units, physical steps and conversion-gain switch points remain unresolved.

Firmware 9.31 and 9.75, 32-bit builds (READ): The compiled camera backend sets maximum gain 400 for the inspected primary-camera model branches and 600 for the Pro secondary-camera branches. These are software capability values; fitted sensors and deployment of every conditional model/architecture combination remain unresolved. The gain setters check the upper bound; they do not establish one common out-of-range policy across all firmware backends.

Firmware 9.75, 64-bit build (READ): `set_control_value` with name `ISP_Gain` reaches a setter that issues no gain update; its getter reads ISP gain. The functional live-video manual-gain route is `set_setting.isp_gain`, which requires a running video worker and manual exposure mode. Settings requests can be routed to the second-camera process according to the active view or `wide_cam`.

Firmware 9.75, 64-bit build (READ): `set_setting.isp_gain` divides its numeric input by ten for the cached manual parameter and multiplies that parameter by ten for application. The ordinary ISP manual branch calculates a gain multiplier as ten raised to the applied gain divided by 200. This establishes the conversion arithmetic; a universal fitted-sensor physical scale, analogue/digital allocation and quantization remain unresolved.

Firmware 9.75, 64-bit build (READ): Low-level `set_control_value` with name `ISP_Exposure` calls the combined ISP exposure/gain operation with gain zero. `set_setting.isp_exp_ms` instead reapplies the cached manual gain with the new exposure.

Firmware 9.31 and 9.75, 64-bit builds (READ): Camera open requests gain zero. Star-view startup requests model gain 200 for the S30 Plus, S30 Pro, S50 Pro, S50N and S80 software branches; the fallback retains initialized gain 80. These are workflow requests rather than sensor capability defaults or observed per-port values.

Firmware 9.31 and 9.75, 32-bit builds (READ): The inspected star-model selection uses 200 for S30, S30 Pro and S50N, 252 for S50 Pro, and initialized fallback 80. The S50 Pro value differs from the 64-bit branch's 200. Applicability of each software branch to deployed hardware remains unresolved.

Firmware 9.75, 64-bit build (READ): A named `Gain` request queues a page/camera-model configuration write before backend application. Internal integer gain requests bypass that named-setting path. Durable commit and automatic gain reload at a later open or view start remain unresolved.

Android supplied decompilation attributed to app 3.3.2, version code 140 (READ): The live-video manual-exposure dialog offers a numeric gain control and sends `set_setting.isp_gain`. It reads the selected main/second-camera `isp_gain` and `isp_range_gain`, with fallback value zero and range zero to 400. Full source/APK equivalence and every upstream mode/model/expert gate remain unresolved; these paths do not establish ordinary star-stack or modern-plan gain UI.

iOS app 3.4.1, build 2, arm64 (READ): The inspected manual live-video interface offers a numeric gain control, takes the selected camera's range from `isp_range_gain` with fallback zero to 400, and sends integer `set_setting.isp_gain`. Scenery and solar main/second-camera adjustment actions wire that callback. The solar main adjustment action has a first-rendered-video-frame gate. Complete mode/model/expert coverage remains unresolved.

iOS app 3.4.0, build 4, arm64 (READ): The inspected gain request builder also sends `set_setting.isp_gain`. Full UI parity with 3.4.1 build 2 remains unresolved.

Firmware 9.75, 64-bit build (READ): Gain-bearing reporting surfaces have distinct sources: `get_setting.isp_gain` prints cached manual state, the Gain and ISP_Gain control getters call their respective backends, and the inspected device-state gain field prints the model star-gain constant. Star-view detail and event-enabled legacy exposure start paths can report sampled camera gain. Complete shot-info/Stack schemas, synchronization between surfaces and correspondence to a particular sensor frame remain unresolved.

## Interactions

| Action | Stops or blocks |
|---|---|
| `close_camera` | ViewPlan, live stack, view, exposure |
| `iscope_start_view` | previous view worker and exposure |
| any view-stage starter | current view stage |
| `iscope_stop_view` (full) | all view workers; may close the focuser |
| running ViewPlan | blocks `iscope_start_view` / `iscope_stop_view` (536) |
| 3PPA running | blocks `start_exposure` (210) |
| planet stack running | blocks `start_exposure` (524) |
| exposure running | blocks a second `start_exposure` (206) |

## Errors

Codes specific to this chapter's flows: 102, 105, 106, 107, 109, 204, 206, 207, 208, 209,
210, 212, 213, 300, 318, 524, 536. Messages come from the shared table; see each card.
Worker errors after a "started" reply arrive only in events (`fail` with `error`/`code`).

## Not covered or unresolved

- Meaning of `set_isp_fps` 0 and when the camera reads it.

- Per-camera values of the two camera-supplied limits (maximum gain, maximum exposure) and the
  camera library's handling of out-of-range values (R17, R17d).
- Which child functions appear under View in each mode.
- AVI recording ([`start_record_avi`](../../docs/control/methods/start_record_avi.md)) and RTMP
  streaming belong to the media chapter.

## Appendix: Validating on a live device (non-normative)

1. `get_camera_state`, then `open_camera`; expect `CameraStateChange`.
2. `iscope_start_view {"mode":"scenery"}`; record the order of reply and `View` event.
3. `start_exposure` twice; expect 206 on the second.
4. `stop_exposure {"wait":false}`; record which `Exposure` shape arrives.
5. `iscope_stop_view`; confirm the resent `View` detail.
