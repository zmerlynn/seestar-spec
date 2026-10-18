# Stacking

Scope: live (real-time) stacking on the star view, planet stacking of a recorded file, batch
stacking of stored frames, and saving or exporting the results. It sits above the view and
exposure layer ([viewing-and-exposure.md](viewing-and-exposure.md)) and uses calibration frames
from [calibration-frames.md](calibration-frames.md). Event framing is in
[events/families.md](events/families.md). Plans that stack automatically are in
[plan-scheduling.md](plan-scheduling.md). Per-method detail stays in the catalog cards.

App names. Live capture: “Starry Sky” (`capt_type:stack`, INFERRED), “Star Trails” (`startrails`),
“Time-lapse” (`timelapse`), “Live” enhancement versus continuous capture (INFERRED), “Freeze Ground”
(`scene_separate`, with its duration), “Save Meteor Frames”, “Trail Rejection”
(`airplane_line_removal`), “RAW Denoise” (`wide_denoise`), “Star Distortion Correction”
(`star_correction`), “Save each frame” and “Save all frames” (`save_discrete_ok_frame`,
`save_discrete_frame`), “Execute enhancement after GOTO” (`stack_after_goto`), and the wide framing
presets “Original Size”, “8K Portrait”, “8K Landscape” and “180° Landscape” (`wide_size_index` 0 to
3). “DBE” matches `dbe_enable`, but the app also does DBE locally (INFERRED). Post-processing: “Deep
Sky Stack” (batch `deepsky`), “Star Trail Stacking” (batch star-trail tasks), “Comet Nucleus
Stacking” (batch `comet`, INFERRED), “Video Stacking” of a “Planet” or “Solar or Lunar surface”
(planet stack), and the trail styles “Classic Star Trails”, “Comet Trails” and “Generate Both”
(maximum, decay, both; INFERRED). The app's “AI Enhance” runs on the phone and is not this device
processing. Names are the English strings of iOS app 3.4.0; links are READ (app call sites) unless
marked.

## Conventions

As in [viewing-and-exposure.md](viewing-and-exposure.md#conventions): RFC 2119 words bind
clients; labels READ, OBSERVED, INFERRED, unresolved; READ is the 64-bit build of firmware
9.31 unless stated. A `start_*` success reply means a worker was launched.

Basis: static analysis of firmware 9.31 / app 3.3.2, with firmware 9.75 / app 3.4.0 deltas marked as such.

## The three stackers

| Stacker | Function name | Input | Started by | Event |
|---|---|---|---|---|
| Live stack | `Stack` (view stage 3) | frames from the running camera | [`iscope_start_stack`](../../docs/control/methods/iscope_start_stack.md), [`start_stack`](../../docs/control/methods/start_stack.md) | [`Stack`](../../docs/control/events/Stack.md) |
| Planet stack | `PlanetStack` | one video or image file | [`start_planet_stack`](../../docs/control/methods/start_planet_stack.md) | [`PlanetStack`](../../docs/control/events/PlanetStack.md) |
| Batch stack | `BatchStack` | a stored file list | [`start_batch_stack`](../../docs/control/methods/start_batch_stack.md) | [`BatchStack`](../../docs/control/events/BatchStack.md) |

Only one live stack exists. The three stackers exclude each other partly ([Planet stack](#planet-stack)). READ.

## Live stack

### Sequence

```
 client                                    device
   | set_stack_type {type:"light"} -------->|  259 if Stack working
   |<------------------------- result 0     |
   | iscope_start_stack {restart:true} ---->|  259 if running; else clear stack
   |<------------------------- result 0     |  view stopped, mode 0, page 0, Stack worker started
   |<------------------------- View  working
   |<------------------------- Stack state=frame_complete ... (per frame)
   |<------------------------- Stack F working (stacked_frame, dropped_frame, ...)
   | save_stack ------------------------->  |  267 if nothing stacked
   |<------------------------- result 0     |  save thread started
   |<------------------------- SaveImage start ... complete | "save fail"
   | iscope_stop_view {stage:"Stack"} ----->|
   |<------------------------- Stack F cancel
```

R1. [`set_stack_type`](../../docs/control/methods/set_stack_type.md) selects the frame type
(`light`, `dark`, `bias`, `flat`; case-insensitive). `autoexp` is read only for `flat`. Errors:
105 missing type, 209 unknown name, 106 malformed `autoexp` for flat, 259 while the Stack
function works (even for the same type). READ. Changing away from a calibration type clears
the stack. READ. A client MUST set the type before starting the stack, not during it.

R2. `iscope_start_stack` starts the Stack stage. With `restart` true it fails with 259 if Stack
is already running, otherwise clears the stack first. Without `restart` it may leave a running
stack untouched and still reply 0. READ. On the 64-bit build an explicit `restart:false` and
an omitted `restart` set different internal continue flags; a client that wants to continue
SHOULD send `false` explicitly. READ.

R3. `start_stack` is the older starter: it starts view stage 3 and returns 0 at once if that
stage already runs; otherwise 318 if the camera is closed. READ. It has no `restart` handling.

R4. Neither starter has a ViewPlan guard. READ. A client SHOULD NOT start a live stack while a
plan runs.

R5. [`stop_stack`](../../docs/control/methods/stop_stack.md) sets the capture error to 253 and
stops the function named `Stack`; it always returns 0. `iscope_stop_view {"stage":"Stack"}`
has the same effect through the view layer. READ.

R6. [`clear_stack`](../../docs/control/methods/clear_stack.md) clears counts with no
running-state guard. READ. A client SHOULD stop the stack before clearing.

R6a0. Firmware 9.75, lens shading: a generic centred crop replaces the 9.31 special case for
3840-row frames. The shading map is rebuilt when the frame size does not match, a 3000 by 4000
entry guard exists, and distortion correction requires a 3840 by 2160 frame. The factory
constants read from the EEPROM are unchanged. READ (64-bit); the 32-bit build was not checked.
Firmware 9.75 star-trail decay is decoded in [Sky replay and star-trail decay (firmware 9.75)](#sky-replay-and-star-trail-decay-firmware-975) (R8b to R8f) and the comet key frame
in [Batch stack](#batch-stack) (R20 to R20c). New 9.75 item not decoded: Alpaca enable-state save and restore.
The stack event builder was not verified.

R6a. Dark and flat calibration of live-stack frames happens when the frame is read, before
stacking, and only while the `frame_calib` setting is on (default off, not persisted). The
master dark used is the one for the current stack exposure. Depending on model, `expert_mode`,
`auto_master_dark` and `stack.wide_denoise`, stack start may first run a blocking dark capture.
READ. Details: [calibration-frames.md](calibration-frames/dark-library.md#building-the-dark-library) R6e to R6g. The
frame type from `set_stack_type` does not change that calibration step. READ. Whether the
stacker's own dark input is ever loaded during a live stack was not traced.

R6b. Filter wheel and the live stack (wheel models). The stack remembers the wheel slot its
frames were taken at. When a live stack starts and frames are already stacked, the device waits
up to 1000 ms for the wheel to stop; if the slot now differs from the remembered one, the stack
is cleared first. `is_stacked` runs the same check without clearing and reports that a restart
is needed. A live stack in photometry mode moves the wheel to slot 1 (`IRCUT`) when its
reference stars load, and moves it back when the stack ends. READ. `iscope_start_stack` itself
starts the star view stage: it can stop the current view and relaunch the View worker, and the
View worker's star-mode start moves the wheel to the saved star-view slot
([focus-and-filter R22d](focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves)).
READ (call path). A stack start therefore can move the wheel: on an S50 Pro, after the stack
stage was stopped and the wheel set to slot 0, `iscope_start_stack {restart:true}` produced a
`View` working event and moved the wheel from 0 to 1 before the stack started. OBSERVED
2026-10-16.

Which stack starts relaunch the View worker. Both `iscope_start_stack` and `start_stack` reuse
the running worker only when it is already in the Stack stage; `iscope_start_stack
{restart:true}` in that state gives 259 ([Interactions](#interactions)). Any other start relaunches the worker, and
the relaunched worker restores the saved star-view slot before its first frame. It waits for the
move, then sets gain and tracking, then runs the autofocus check and automatic exposure, then
stacks. READ (both builds, except that the 32-bit build has no automatic-exposure step; R6e). The restore is skipped only when no wheel is fitted, when no slot 1 or 2 has been
saved, or when the wheel is already at the saved slot. Stopping a star-mode view saves the slot
when it is 1 or 2, so a wheel at 1 or 2 stays put, and a wheel at 0 goes back to the last saved
1 or 2. READ
([focus-and-filter R22g, R22h](focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves)).

A client that needs slot 0 SHOULD set it after the stack has started; the first frame taken
after that may span the client's own move. INFERRED. The live stacker has no test for a dark slot: frames taken at slot 0 are stacked
like any other. Only capture runs test for it.
READ (both builds). Other automatic wheel moves, and how
capture runs treat dark-slot entries, are in
[focus-and-filter.md](focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves).

R6c. Tracking and the below-horizon stop. The live stack checks the mount's tracking state once
before its first frame and again on every stacking pass. It asks the guider for the tracking
state (`scope_get_track_state`, 10 s timeout); when the reply reports not tracking with reason
`below horizon` (270) or `alt exceed limit` (527), the stack worker quits and saves no frame for
that pass. Any other reason, or a tracking reply, lets the stack continue. The stop follows the
guider's tracking reason, which comes from the mount controller; the live stack never evaluates
the target altitude itself. A few internal modes (star-trail capture among them) skip this
tracking check. READ (both builds; the 32-bit build makes the same test inline in the stack
worker). How the mount's below-horizon reason reaches the guider and the
imager `Alert` that follows are in
[tracking-park-and-state R36a](mount-and-motion/tracking-park-and-state.md#park-home-and-the-arm).
OBSERVED 2026-10-16 (S50 Pro): with a view running, parking the arm produced `ScopeTrack` off
`below horizon` 270 and an imager `Alert` 270. OBSERVED 2026-10-16 (S50 Pro): with the arm
closed, `iscope_start_stack {"restart":true}` relaunched the view, moved the wheel and started
the stack. About 3 s later it reported a `Stack` failure `below horizon` with code 270, and no
frame was saved.

R6d. Lens-shading correction (S30 Pro, S50 Pro, S30 Plus-class). When the live stack runs in
the wide-camera process of these models, the stacker applies a per-unit lens-shading
(vignetting) correction to every 16-bit raw frame. Only the model and the camera gate it: no
setting, no `frame_calib` and no frame type. The main camera never gets it, and the batch and
planet stackers do not apply it. READ. That this camera is the wide-angle camera is INFERRED
from internal naming. All three per-frame paths of the live stack apply it: ordinary frames,
scene shooting and the starry-landscape variant. READ (64-bit; the 32-bit build has the same
three call sites, READ, but the rest of it was not checked).

- Source. The table is factory data, read over I2C from an on-board EEPROM: 2312 bytes, parsed
  as 1156 big-endian 16-bit words that form four 17 × 17 grids, one per Bayer position. There is
  no fallback table or file. READ.
- Map. Each grid is rotated a fixed 90°, smoothed with a 3 × 3 Gaussian and upscaled with
  Lanczos interpolation to 3000 × 4000. For 3840-row frames it is cropped to the central
  2160 × 3840. Each grid is then divided by its own mean, so each channel's gains average 1.
  Each pixel takes the gain from the grid of its Bayer position. The rotation does not follow
  any orientation setting. READ.
- Formula. out = 4098 + gain × (in − 4098), clamped to 0..65535; 4098 is a fixed pedestal.
  The correction is multiplicative. READ.
- Order. It runs after the calibration at frame read (R6a) and after the stacker's own dark
  step, and before debayering and lens-distortion correction. For ordinary frames and scene
  shooting it follows the wide camera's raw AI denoise; a frame whose denoise fails is dropped
  before this step. In the starry-landscape variant it comes before the denoise. READ.
- Saved sub-frames. The correction changes the frame buffer in place, and the live stack later
  writes its per-frame FITS from that buffer. Saved wide-camera sub-frames therefore carry the
  correction, and the denoise where it ran first. READ.
- Caching and failure. The map is built at the first frame and kept for the stacker's
  lifetime. If the EEPROM read or parse fails, the frame continues uncorrected and the next
  frame retries the read; the stack does not fail. A frame whose size differs from the cached
  map, or that is not 16-bit, is passed uncorrected, and the map is not rebuilt. READ.
- Reporting. No reply, setting, event or FITS keyword says whether the correction ran. Saved
  files carry only the general wide-camera keyword `WIDECAM`. READ (absence in the header
  writer and handlers). A client MUST NOT apply its own flat for vignetting to such sub-frames
  on the assumption that they are uncorrected.

R6e. Initialisation at stack start. When a View worker enters the Stack stage in the
main-camera process, it runs these steps in order, each blocking (READ, both builds, with the
32-bit differences noted below):

1. Wheel restore, gain and tracking (R6b).
2. The `Initialise` function: the automatic polar-alignment check when that stack option is on;
   the automatic master dark when its gate holds
   ([calibration-frames R6f](calibration-frames/dark-library.md#building-the-dark-library)); the automatic bias when
   `stack.wide_denoise` is on ([calibration-frames R11b](calibration-frames/frames-and-interactions.md#selecting-frames));
   with `stack.wide_denoise` off, the master-dark check under the wide-denoise-off gate of R6f;
   then the initial autofocus.
   Firmware 9.75 (64-bit): the master-dark step is replaced by a temperature dark library check
   and preparation, and the order is dark library, bias (wide denoise), polar alignment, then
   autofocus. READ (order); that the old blocking dark capture is the library's fallback is
   INFERRED. The 9.31 wording of this step applies to firmware 9.31.
3. The main autofocus, the temperature-triggered autofocus and automatic exposure.
4. The Stack worker, which sends `Stack` `start` and then makes its first tracking check (R6c).

A master dark or bias is skipped when one already exists: the dark when the library holds a
usable master for the current exposure, the bias after it has once succeeded in this run of the
imager service. The initial autofocus runs once per imager run. It is skipped after a goto
autofocus succeeded, and in `expert_mode` when the stack's automatic autofocus is off. READ. An
`Initialise` failure is recorded as the plan error and the start continues with step 3. READ
(64-bit); that this holds for every failure branch is INFERRED. The wide-camera process runs
its own autofocus path instead and never runs `Initialise`. An internal stack-simulation
setting also skips it. READ. Because step 2 ends before `Stack` `start`, a failure that the Stack
worker reports seconds after `start` (such as 270, R6c) comes after any bias or dark built for
that start. READ. A start that reuses a worker already in the Stack stage (R6b) does not
repeat these steps. INFERRED from the worker reuse.

The 32-bit build differs in two points. Step 3 has no automatic exposure: the 32-bit imager
contains no stack automatic-exposure routine, and the Stack stage goes from the autofocus checks
straight to the Stack worker. The master-dark gates of step 2 follow the 32-bit rule of
[calibration-frames R6f](calibration-frames/dark-library.md#building-the-dark-library). READ (32-bit).

### Queries

| Method | Returns | Errors |
|---|---|---|
| [`get_stack_info`](../../docs/control/methods/get_stack_info.md) | `{width, height}`; with `info_type:"fit_header"`: `{fit_header, save_fit_header, base_name}` | 267 with no frames |
| [`is_stacked`](../../docs/control/methods/is_stacked.md) | `{is_stacked}` | may wait up to 1000 ms |
| [`get_view_state`](../../docs/control/methods/get_view_state.md) | View subtree including Stack | none specific |

R7. `is_stacked` can block up to 1000 ms. The app uses it before deciding whether to restart a
stack. READ (grade differs between builds; see the card).

### Stack events

[`Stack`](../../docs/control/events/Stack.md) has two producers on the same event name. A
client MUST tell them apart by `state`.

| Producer | States | Members |
|---|---|---|
| Custom (stack-frame notifier) | `frame_complete` (`start` listed by the app; no producer found) | `frame_type`, `stacked_frame`, `dropped_frame`, `total_frame`, optional `file_name`, `lapse_ms`, and `error`/`code` always (even code 0) |
| Function (F) | F states | `frame_errcode`, `stacked_frame`, `dropped_frame`, `can_annotate`, `cont_capt_frame`, `jpg_name`, `angle`, `output_file`, and on the 64-bit build `scene_shooting`, `auto_exp_us`, `file_saved`, mosaic members (`progress`, `stitch_progress`, `part_complete`, `ra_dec`) |

READ. On the 64-bit build the custom notification is sent only as `frame_complete`, once per
accepted frame, by the live-stack worker; no producer of a custom `start` or `fail` was found,
and stack failures surface through the function family. READ (absence) / INFERRED (alternative
path). The 32-bit build was not decoded. A client MUST NOT treat
`code` 0 with an `error` member in a custom Stack event as a failure. OBSERVED (2026-10-12): two wire shapes
matching these producers.

R8. Event cadence follows frame acceptance, not a timer. READ.

### Sky replay and star-trail decay (firmware 9.75)

R8a. Firmware 9.75, app 3.4.0: the `sky_replay` boolean setting
([`set_setting`](../../docs/control/methods/set_setting.md)) makes a live stack also record a replay
video, saved as a `*_stack_replay.mp4` with a thumbnail. The worker, limits and the new codes 551 and
552 are in [function-states.md](function-states.md#sky-replay). Firmware 9.31 has no such setting.
READ.

R8b. Firmware 9.75, app 3.4.0 (64-bit build): the integer `startrail_mode` (stored as
`stack.startrail_mode`, written through the `stack` object of
[`set_setting`](../../docs/control/methods/set_setting.md)) selects the star-trail outputs:
0 the maximum-image video, 1 the decay video, 2 both. A value that is not an integer gives 104;
the wide camera is required (210 on the other camera); a value above 2, negative values included,
gives 209. There is no running-stack check: a change instead clears the stack (the stacker
logs a restart and resets its decay state). The setting is also reset by
[`reset_setting`](../../docs/control/methods/reset_setting.md) (see
[function-states.md](function-states.md#settings-reset)). READ. Firmware 9.31 has no such
setting and no decay output. The 32-bit build shows no `startrail_mode`, decay or duration
strings; that is string-level only and was not checked in the code (unresolved).

R8c0. Firmware 9.75, app 3.4.0: the video of a star-trail session is written only when the
stack setting `save_video` is true; the FITS (and image) save is always the maximum output,
whatever `startrail_mode` says. READ.

R8d. Firmware 9.75, app 3.4.0 (64-bit build): the integer `stack.startrails_duration_min`
limits a star-trail session, in minutes. A non-integer gives 104; the wide camera is required (210);
a running stack gives 259; there is no range check. The default is -1; -1 or 0 means no limit.
The value is copied when the session starts, so a later change does not affect a running
session. When elapsed time reaches the limit the stack worker takes its normal end-of-stack
path. READ. Which final `Stack` state or code announces a session ended this way is unresolved.
The 32-bit build shows no such string (string-level only).

R8e. Firmware 9.75: the decay video uses a fixed factor of 0.987 per accepted frame: the
accumulated image and its brightness map are multiplied by it, and any pixel where the new
frame is brighter is replaced by the new frame. The factor is not configurable and has no
wire member; it affects only the decay output. READ.

R8f. Output names, firmware 9.75, app 3.4.0: mode 0 writes `startrails_video_<ts>.mp4`, mode 1
`startrails_video_decay_<ts>.mp4`, mode 2 both. Batch star-trail tasks use the prefixes
`STS_startrails_` (image), `STS_startrails_video_` (maximum video) and, new in 9.75,
`STS_startrails_video_decay_`. The FITS header keys written by the batch star-trail header update
are unresolved. READ for the names.

R8c. Firmware 9.75, 64-bit build marks a main-camera star request outside ViewPlan as a mosaic-goto source when its target coordinates pass the sentinel tests and its requested scale or rotation exceeds the source thresholds. This marker does not prove that a mosaic was applied or that the goto completed. When stack-start preparation is reached, it converts a marked source only if the current main-camera stack contains frames: it resets mosaic parameters to scale 1, angle 0 and star-map angle 361, clears the stack, selects the ordinary stacker and consumes the marker. An already-running identical stage can return before stage preparation. Successful local `iscope_start_stack` still returns integer 0; the marker adds no reply member or distinct success value. Firmware 9.75, 32-bit preparation has the same flag/frame-count/reset/clear/ordinary-stacker sequence with camera ID 0. READ. Firmware 9.31, 64-bit path has no corresponding source conversion; broader relay/build parity remains unresolved here. Firmware 9.75 also routes
`iscope_start_stack` through a relay-only reduced clone of the common relay check, so it does not
gain the 203 and 524 occupancy outcomes; the same holds for `save_image`, `is_stacked` and
`get_stack_info`. The same relay-only form is used by `start_auto_focuse`, `stop_auto_focuse`,
`iscope_match_target_name`, `iscope_accept_target_name` and others; the occupancy probes are used
only by `start_track_object`, `start_smart_follow`, `start_func`, `start_motion_monitor`,
`start_record_avi` and `start_scan_planet` (see [special-modes.md](special-modes.md)). READ (64-bit
firmware 9.75). The 32-bit behaviour is unresolved.

## Saving

R9. [`save_stack`](../../docs/control/methods/save_stack.md) reads no params. It builds the
stacked image and starts an asynchronous save thread. Errors: 267 (light stack with no frames),
300 (internal frame type 4), refusals in simulator or unsupported capture types (code forwarded
unchanged, possibly 207), 213 with a top-level `fullname` when already saved. READ.

R10. Save completion is reported by [`SaveImage`](../../docs/control/events/SaveImage.md):
`start`, `complete` (with `filename`/`fullname`), or the literal `save fail` (with a space).
Some fail paths carry no `code`. READ. A client MUST match `save fail` exactly.

R11. [`set_image_save_path`](../../docs/control/methods/set_image_save_path.md) selects the
storage (`emmc`, `sd`, `udisk`); 105, 109, 318 (not mounted). Current volumes come from
[`get_image_save_path`](../../docs/control/methods/get_image_save_path.md). READ.

## Export to other storage

```
 client                                 device
   | start_export_image {dst,files,keep} ->|  109/267/209/318/204/268
   |<------------------------- result 0    |  list enumerated, worker started
   |<------------------------- ExportImage state=start
   |<------------------------- ExportImage state=frame_complete (lapse, total)
   |<------------------------- ExportImage state=complete
```

R12. [`start_export_image`](../../docs/control/methods/start_export_image.md) takes an
optional object `{keep, src, dst, files}`. Unknown keys or a non-array `files` give 109; an
empty selection 267; `src` equal to `dst` 209; an unmounted storage 318; a running export 268.
READ. Malformed `src`/`dst` values have no safe defined reply; a client MUST send strings.

R13. `keep:false` permits the worker to delete source files after copying. READ. A client MUST
send `keep:true` unless it intends a move.

R14. [`ExportImage`](../../docs/control/events/ExportImage.md) is a progress event (family P):
`state` (`start`, `frame_complete`, `complete`), `lapse` and `total` (file counts, despite the
name `lapse`; INFERRED), `keep`, `dst_storage`. READ. `complete` is also sent after a stop, so
it does not mean every file was copied. A client MUST compare `lapse` with `total`.

R15. [`stop_export_image`](../../docs/control/methods/stop_export_image.md) blocks until the
worker stops and returns `{success_frame, total_frame}`. READ.

## Planet stack

R16. [`start_planet_stack`](../../docs/control/methods/start_planet_stack.md) takes an object
`{file, mode?, rect?}`. `mode` is lunar (moon), solar (sun) or planet; empty means "detect from
the file name", failing with 102. Errors: 102 (params), 268 (running), 524 (batch stack, View
or continuous exposure conflict), 536 (ViewPlan running), 208 (free space at most 199 MiB),
212. READ. If the free-space query itself fails the disk check is skipped. READ.

R16a. Firmware 9.75, app 3.4.0: the planet-stack parameters (and the compass sensor data used by compass
calibration) gain a member `direction_true`. Only its existence is established; its type and meaning
are unresolved. READ (existence).

R17. Progress is reported by [`PlanetStack`](../../docs/control/events/PlanetStack.md): F plus
`percent` (capped at 99 while working), `procedure_code`, `procedure`, `output_file`,
`input_thn`. READ. The output file name is built from the mode and the current date and time,
with a `.fit` extension. READ.

R18. [`stop_planet_stack`](../../docs/control/methods/stop_planet_stack.md) always returns 0 and
may block until the worker ends. [`clear_planet_stack`](../../docs/control/methods/clear_planet_stack.md)
resets the held result buffers; while the worker runs it returns 207 (not 268). Neither deletes
files. READ.

### Additional planet-stack rules

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.


[`start_planet_stack`](../../docs/control/methods/start_planet_stack.md) takes
`{file, mode, rect}`. `file` (a recorded video name) is required (102). `mode` is `moon`/`lunar`,
`sun`/`solar` or `planet`, case-insensitive; empty means "guess from the file name", and failure
gives 102. `rect` is `[x, y, width, height]` integers; null gives 102; absent means full frame.
READ.

Errors: 268 already stacking; 524 conflict with batch stack, view or continuous exposure;
536 `view plan is already running`; 208 when free space is 199 MiB or less; 212. READ. A failed
free-space query skips the 208 check. READ.

Progress arrives as [`PlanetStack`](../../docs/control/events/PlanetStack.md) function events
with `percent` (integer), `input_thn` (when known) and `output_file` (an object, at success).
A failure is also sent as a simple state event with `code` and `error`. READ. `output_file` is
`{path, files}`: `path` is the directory without a trailing slash and `files` is a one-element
array of `{name, date, thn, type}`, where `name` is relative to the storage root, `thn` names the
thumbnail and `type` is the album file-type code
([album result](../media/files-and-album.md#album-result-and-conversion-details)). Every mode that reports a saved output (live stack, planet stack, batch
stack, wide mosaic, plan results) uses this shape. READ. The output name pattern is
`Video_Stacked_<name>_<date>-<time>.fit`. READ.

Starting a planet stack stops AVI playback. READ.
[`stop_planet_stack`](../../docs/control/methods/stop_planet_stack.md) never errors and may block.
[`clear_planet_stack`](../../docs/control/methods/clear_planet_stack.md) returns 207 while the
worker runs, else clears the result buffers. READ.

## Batch stack

```
 client                                     device
   | set_batch_stack_setting {files} ------>|  persisted list
   | start_batch_stack {task_type,frame_type}|  107/105/102/207/524/536
   |<------------------------- result 0     |
   |<------------------------- BatchStack working (percent, stacked_img, total_img, ...)
   |<------------------------- BatchStack complete (output_file) | fail | cancel
```

R19. The input list is managed with
[`get_batch_stack_setting`](../../docs/control/methods/get_batch_stack_setting.md),
[`set_batch_stack_setting`](../../docs/control/methods/set_batch_stack_setting.md) and
[`del_batch_stack_file`](../../docs/control/methods/del_batch_stack_file.md). The getter prunes
missing files from the stored list (it mutates). The setter replaces the list partially on
error and persists it (258/218 on write failure); 259 while a batch stack runs.
`del_batch_stack_file` deletes files on disk. READ.

R20. [`start_batch_stack`](../../docs/control/methods/start_batch_stack.md), 64-bit build:
`task_type` is `deepsky`, `startrail_image`, `startrail_video` or `comet` (case-sensitive);
`frame_type` light/dark/bias/flat. Omitted params mean deepsky/light; `{}` gives 105; an unknown
task 102; an invalid task/frame pair 207 (startrail forces light; comet requires light). The
32-bit build reads only `frame_type`. READ.
Firmware 9.75, app 3.4.0: the batch star-trail list carries an integer `batch_startrails_mode`
(0 to 2, same meaning as `startrail_mode`, R8b; names in R8f). Both list methods carry it, see R20a.

R20a. Firmware 9.75, app 3.4.0 (64-bit build): [`set_batch_stack_setting`](../../docs/control/methods/set_batch_stack_setting.md)
accepts, besides `type` and `files`, an optional string `key_frame` for the `deepsky` and `comet`
lists and an optional integer `batch_startrails_mode` (0 to 2) for the `startrail` list; a wrong
type or range gives 102. A `key_frame` that is not in the list is reset to the first entry when the
list is stored. [`get_batch_stack_setting`](../../docs/control/methods/get_batch_stack_setting.md)
returns `key_frame` (deepsky, comet) or `batch_startrails_mode` (startrail) next to `files`.
Each of the three types is cached and persisted separately; the comet list has its own file.
Firmware 9.31 shared one list and one file between deepsky and comet; that is no longer true in
9.75. The comet batch uses the key frame as the reference frame: before registration it moves the
key frame to the front of the candidates. READ. The 32-bit build shows none of these strings,
so its list handling may differ (string-level only, not traced).

R20b. Firmware 9.75, app 3.4.0: a comet batch is the only comet stacker. There is no live comet
stack and no comet start or stop method; the task takes light frames only and the result is saved in
the deep-sky folder. `can_comet_post_stack` in `get_device_state` is just a per-model capability bit
(R5c of [maintenance.md](maintenance.md)), not a mode. READ (a negative result from a string and
handler analysis, not an exhaustive proof).

R20c. Firmware 9.75, app 3.4.0: a comet batch is limited to 200 input frames, the constant
`comet_max_frame_num` reported by `get_setting` (not settable). The count is checked in three
places: at `start_batch_stack` (input list above 200), in the worker on the input list, and again
after the list is expanded. Each raises thread-local error value 204 `out of limit`. READ for the
places and the code. The `start_batch_stack` reply code 204 for the first place is INFERRED from the
stored thread-local error value; whether the worker-side failures reach the `BatchStack` event with
204 is unresolved. A new preflight scans the list for the first frame that contains a comet and
skips frames that are not valid FITS, cannot be loaded or show no comet; if none is found it fails
with 9005 (`comet not found`), and a detector initialisation failure gives 9002 (details in
[errors.md](errors.md)). With too few usable candidates the worker raises 9004. An empty non-comet
list gives 267. READ. Firmware 9.31 had no limit and no preflight.

R21. There is no immediate empty-list check; an empty list fails in the worker. READ.

R22. [`BatchStack`](../../docs/control/events/BatchStack.md): F plus `percent`, `frame_type`,
`task_type`, `stacked_img`, `total_img`, optional `remaining_sec` (seconds, INFERRED),
`input_thn`, `output_file` (object), and on the 64-bit build `keep`. READ. `output_file` is set on
the completing function event after the result is saved, with the shape in
[planet-stack output](stacking.md#planet-stack); the comet dual-stack variant reports
its own the same way. READ. The 32-bit build lacks `startrail_video` and `keep`.

R23. [`stop_batch_stack`](../../docs/control/methods/stop_batch_stack.md) joins the worker and
always returns 0. [`clear_batch_stack`](../../docs/control/methods/clear_batch_stack.md) returns
259 while running; otherwise it sets a clear flag and deletes nothing. READ.

## Interactions

| Running | Blocks | Code |
|---|---|---|
| Live Stack | `set_stack_type`; `iscope_start_stack {restart:true}`; `set_calib_frame` of the same frame type | 259 |
| Live Stack or dark-library worker | `start_batch_stack` | 524 |
| ViewPlan | `start_batch_stack`, `start_planet_stack` | 536 |
| BatchStack, View or continuous exposure | `start_planet_stack` | 524 |
| PlanetStack | `start_exposure`, `start_record_avi` | 524 |
| BatchStack | `clear_batch_stack`, `set_batch_stack_setting` | 259 |
| Export running | second `start_export_image` | 268 |

A new view or view stage stops the live stack ([viewing-and-exposure.md](viewing-and-exposure.md#interactions)).
`close_camera` stops it too. A wheel slot change between stack runs clears the stack at the
next start (R6b). The live stack also quits on its own when the mount stops tracking below the
horizon or over the altitude limit (R6c).

## Errors

Chapter codes: 102, 105, 106, 107, 109, 204, 207, 208, 209, 212, 213, 218, 258, 259, 267, 268,
300, 318, 524, 536. Worker failures after "started" arrive in events only.

## Not covered or unresolved

- The custom Stack states sent by the 32-bit build; reachability of every F state per worker.
- Whether the live stack rejects frames after a bin or subframe change (batch stacking stops at a
  file whose dimensions differ from the first, READ).
- Ordering of `SaveImage` against the `save_stack` reply.
- Grade of `is_stacked` on the 32-bit build.
- Which code path emits the `Stack` failure for the below-horizon stop (R6c). The 270 case is
  OBSERVED, the 527 case is not, and neither is READ.
- Firmware 9.75: the wire effect of the mosaic goto source (R8c), and the frame cap of sky replay.
- Firmware 9.75: the final event or state when `stack.startrails_duration_min` ends a session (R8d); the FITS header keys of the batch star-trail header update (R8f); how the comet limit and the worker failures 204, 9004 are reported in `BatchStack` events (R20c); comet-specific FITS or JSON header keys (none found). The 32-bit build for star-trail modes and the comet limit is string-level only.
- Firmware 9.75 imager additions seen only as new symbols and not decoded, wire effect unresolved: a circle/disk realtime stabiliser with a selector; stack-exposure reconciliation for the mount mode and stack exposure notification; track-state restore; annotate waiting; Wi-Fi station check; device-model query; batch progress and stack header helpers; compass residual failure code and automatic compass calibration start; motion-record MP4 result; H.264 packet and colour-metadata helpers and RTMP ROI scaling; further IMU drivers and sampling-frequency setters; album helpers for scenery and video-stack names. Guider and updater symbol differences were not diffed.
- Lens-shading correction (R6d): when the stacker object, and so the cached map, is reset; how
  the process's camera id is set; the 32-bit build beyond its call sites.

## Appendix: Validating on a live device (non-normative)

1. `set_stack_type {"type":"light"}`, `iscope_start_stack {"restart":true}`; log `Stack`
   shapes and which carry `error`/`code` with code 0.
2. `set_stack_type` while stacking; expect 259.
3. `save_stack` twice; expect 213 with `fullname` on the second.
4. Export with `keep:true` and stop it mid-way; confirm `complete` with `lapse < total`.
