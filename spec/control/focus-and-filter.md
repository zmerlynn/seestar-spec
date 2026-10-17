# Focus and filter wheel

Scope: the electronic focuser (open, move, settings), autofocus, and the filter wheel. It sits
above camera control ([viewing-and-exposure.md](viewing-and-exposure.md)) and is used by
autofocus inside goto flows ([solving-and-annotation.md](solving-and-annotation.md)) and by
calibration ([calibration-frames.md](calibration-frames.md)). Event framing is in
[events/families.md](events/families.md). Per-method detail stays in the catalog cards.

## Conventions

As in [viewing-and-exposure.md](viewing-and-exposure.md#conventions): RFC 2119 words bind
clients; labels READ, OBSERVED, INFERRED, unresolved; READ is the 64-bit build of firmware
9.31 unless stated.

Basis: static analysis of firmware 9.31 / app 3.3.2.

## Focuser

### Lifecycle

```
 client                                  device
   | get_connected_focuser ------------->|  list
   | open_focuser ---------------------->|  210 / 201; may start an init move
   |                                     |  polls open state up to 30 s (100 ms steps)
   |<------------------------- result 0  |
   | get_focuser_state ----------------->|  {state: close|idle|moving, name, id, max_step_range}
   | move_focuser {step, ret_step?} ---->|  104 / 318 / 300
   |<------------------------- result 0 or {step}
   |<------------------------- FocuserMove complete (position)
   | stop_focuser ---------------------->|  318 / 300
   | close_focuser --------------------->|  201 on close failure
```

R1. [`open_focuser`](../../docs/control/methods/open_focuser.md) returns 0 when already open,
210 on a wide model that cannot autofocus, 201 when the open fails. It may start an initial move
and then polls the open state for up to 30 s in 100 ms steps. READ (the poll limit; total reply
latency was not measured). A client MUST allow for that delay.

R2. [`get_focuser_state`](../../docs/control/methods/get_focuser_state.md) reports `close`,
`idle` or `moving`, the fixed name of the built-in focuser, id 0 and `max_step_range`. A
failed internal poll is reported as `idle`, not as an error. The `close` reply omits `name`, `id`
and `max_step_range`. READ.

R3. [`move_focuser`](../../docs/control/methods/move_focuser.md) takes an integer `step` (104
otherwise) and returns without waiting for motion. With `ret_step:true` the result is
`{step}` (the clamped step) instead of 0. The move is issued before the optional step lookup,
so an error from that lookup does not mean nothing moved. On wide-camera models it may be
relayed to the peer process. READ.

R4. [`get_focuser_position`](../../docs/control/methods/get_focuser_position.md) returns an
integer UI step, or `{step}` when the object form is requested; 318 closed, 300 internal.
[`stop_focuser`](../../docs/control/methods/stop_focuser.md) gives 318 or 300.
[`close_focuser`](../../docs/control/methods/close_focuser.md) gives 201 on failure. READ.

R5. [`FocuserMove`](../../docs/control/events/FocuserMove.md): F plus a custom `complete` with
`position` and optional `route`. A view refresh can also send `complete` with `position`
without a client move. READ. A client MUST NOT assume one `complete` per `move_focuser`.

### Values and settings

R6. [`get_focuser_value`](../../docs/control/methods/get_focuser_value.md) and
[`set_focuser_value`](../../docs/control/methods/set_focuser_value.md) match the name by
case-insensitive substring against `max_step`, `backlash`, `reset_step`. Errors: get 105, 109,
318, 210, 300; set 105, 104, 109, 318, 210, 300. On the 64-bit build only `max_step` reads
successfully. READ.

| Name | get | set |
|---|---|---|
| `max_step` | value | 210 |
| `backlash` | 300 on the 64-bit build | 300 on the 64-bit build |
| `reset_step` | 210 | resets the position register; no motion |

A client SHOULD NOT use `backlash` on the 64-bit build.

R7. [`get_focuser_caps`](../../docs/control/methods/get_focuser_caps.md) returns 318 when
closed. With the focuser open the handler raises an internal error on a null value that nothing on
the command path catches. READ. The imaging process is then expected to terminate without a
reply. INFERRED. A client MUST NOT send this request while the focuser is open, and MUST treat a
lost connection after it as this failure.

R8. [`get_focuser_setting`](../../docs/control/methods/get_focuser_setting.md) /
[`set_focuser_setting`](../../docs/control/methods/set_focuser_setting.md) hold the autofocus
policy (14 fields). Setter errors: 107 non-object, 109 unknown key, 204 out of range. READ.

| Field | Range | Field | Range |
|---|---|---|---|
| `fine_step` | 0..5000 | `coarse_step` | 0..5000 |
| `af_temp_span` | 0..50 | `af_init_step` | 0..500 |
| `af_bin` | 1..max bin (checked only if changed) | `af_exp_sec` | 0..30 |
| `af_time_span_hour` | 0..24 | booleans | `af_temp_change_on`, `af_time_change_on`, `af_wheel_change`, `af_before_capture`, `af_merid_flip`, `af_track_on`, `af_only_one` |

The getter returns all 14 fields, plus optional `position` and `max_step`; a member whose read
fails is omitted while the envelope code stays 0. It works with the focuser closed. READ. The
setter also gives 109 for a wrongly typed value and rejects negatives; `{}` validates and
succeeds. A configuration-write failure is returned (a zero code becomes 207), and the in-memory
value can change even when the write fails. READ. `af_temp_span` is in degrees Celsius and
`af_time_span_hour` in hours since the last autofocus. READ. Step and second units are INFERRED
from the names.

R9. [`reset_factory_focal_pos`](../../docs/control/methods/reset_factory_focal_pos.md) takes
`{wide_cam?}` and returns `{focal_pos}`. With `wide_cam:true` it gives 210 when the model can
autofocus the wide camera, is relayed to the peer process from the main process, and gives 300 in
an unsupported process state. 236 (`xml item is not found`) when the factory value is missing or
not positive. It checks no open state and causes no motion. READ. `focal_pos` is a logical focuser
position, not a length (INFERRED).

## Autofocus

```
 client                                     device
   | start_auto_focuse ------------------->  |  318 (focuser closed) / 268 (AF running)
   |<------------------------- result 0     |  AF worker or view stage 1 started
   |<------------------------- AutoFocus working (center_xy, position)
   |<------------------------- FocuserMove ... (per step)
   |<------------------------- AutoFocus complete (result{curve,points,...}) | fail
   | stop_auto_focuse ------------------->  |  capture error := 253
   |<------------------------- result 0     |
```

R10. A client MUST open the focuser before
[`start_auto_focuse`](../../docs/control/methods/start_auto_focuse.md) (318 otherwise). A second
start while AF runs gives 268 outside RTMP streaming mode; in RTMP mode the old AF thread is
stopped and replaced. On wide-camera models the call may first be relayed to the peer process.
READ. The method name is spelled `start_auto_focuse`; the app sends it
with null params.

R10a. Firmware 9.75 (64-bit): `start_auto_focuse` and `stop_auto_focuse` first test whether the
wide camera can run autofocus, then call the full relay and occupancy check instead of the 9.31
test "view mode == 1". The call form is the relay-only one (check type 0, relaying enabled): it relays the call to the peer
process when needed but runs no occupancy probe, so these two methods gain no 203 or 524 from it
(READ, 64-bit; an earlier statement that they do is withdrawn). The occupancy probes with
`is_func_occupy_mount` (203) and `is_func_work` for `AviRecord` and `MotionMonitor` (524) belong
to the other call forms listed in [special-modes.md R21](special-modes.md#object-tracking). When the check
refuses it has already replied and the handler returns. READ (call), INFERRED (wire effect). The local
body and R22d are unchanged: stop still sets 253 and stops autofocus. Motion detection is
paused while autofocus runs, and the autofocus streaming thread applies the 2x2 binning of `preview.raw_bin2` when that setting is true (media image-sockets R11b). A
new string, `lp_position`, appears in the autofocus code and is unresolved. The 32-bit build
was not checked.

R11. Depending on mode, the starter runs a named AF worker or view stage 1. Stage 1 stops the
current view stage ([viewing-and-exposure.md](viewing-and-exposure.md#view-stages-started-directly)).
READ. A client MUST expect a running live stack to stop when autofocus starts in stage form.

R12. [`stop_auto_focuse`](../../docs/control/methods/stop_auto_focuse.md) sets the capture
error to 253 and always returns 0. It may be relayed to the peer process on wide-camera models
and can wait for the worker to finish with no bounded timeout. READ. A client SHOULD NOT treat a
slow reply as a failure.

R13. [`AutoFocus`](../../docs/control/events/AutoFocus.md) has an F producer and a legacy
producer (`start`, `working`, `complete`, `fail`). Members: `center_xy`, `position`,
`result{curve, points, x_scale, y_scale, status_flag, last_point?}`, `error`/`code`. READ.
`position` is sent only by the legacy producer. `points` lists `[step, value]` samples;
`x_scale` and `y_scale` are the plotting ranges; `curve` holds three fitted coefficients (a
quadratic, INFERRED). `status_flag` is 1 on the first report and 2 or 3 later; what separates 2
from 3 is unresolved. `last_point` is `[position, value]`, the final focuser position and its
focus metric. READ (shapes); INFERRED (the metric is star size).

R14. Autofocus may also run as a child of [`AutoGoto`](../../docs/control/events/AutoGoto.md) ([Autofocus](#autofocus) of
[solving-and-annotation.md](solving-and-annotation.md)) or of a ViewPlan, driven by the
`af_*` settings. READ (child events precede goto completion). In a capture run, before a light
frame through a non-dark filter, autofocus runs for the first enabled trigger that matches, in
this order: before the first capture (`af_before_capture`), after a filter change
(`af_wheel_change`), after a focuser temperature change larger than `af_temp_span`
(`af_temp_change_on`), and after `af_time_span_hour` hours (`af_time_change_on`). After an
automatic meridian flip, `af_merid_flip` runs autofocus when the focuser is open. A failed
triggered autofocus does not stop the capture run. `af_only_one` is passed to the focus
algorithm and is not a trigger; nothing reads `af_track_on`. READ.

## Filter wheel

### Lifecycle and position

```
 client                                     device
   | get_connected_wheels -------------->    |  [{name:"EFW", id:0}] (always)
   | open_wheel [id?] ------------------->   |  202 on id mismatch; moves toward position 1
   | set_wheel_position [n] ------------->   |  107 / 204 / 318 / 203
   |<------------------------- result 0      |  WheelMove worker started
   |<------------------------- WheelMove start
   |<------------------------- WheelMove complete (position) | fail
   | get_wheel_position ---------------->    |  -1 while moving
```

R15. [`get_connected_wheels`](../../docs/control/methods/get_connected_wheels.md) always
returns one entry. READ. A client MUST NOT infer that a wheel is fitted from this list; use
the model capabilities and [`get_wheel_state`](../../docs/control/methods/get_wheel_state.md).

R16. [`open_wheel`](../../docs/control/methods/open_wheel.md) takes an optional integer
(default -1) and starts a move toward position 1. 104 for a non-integer or null id. Opening
the already open id is a no-op success; a different id gives 202. READ.
[`close_wheel`](../../docs/control/methods/close_wheel.md) always returns 0.

R17. [`set_wheel_position`](../../docs/control/methods/set_wheel_position.md) accepts 0..2
(204 otherwise), 107 malformed, 318 closed, 203 moving. The move runs asynchronously. READ.
[`get_wheel_position`](../../docs/control/methods/get_wheel_position.md) returns -1 while
moving and 318 when closed.

R18. `get_wheel_state` reports `close`, `idle` or `moving` (`calibrating` and `error` exist
only in handler branches), `id`, `unidirection`. A nested `error`/`code` can appear inside the
result while the envelope `code` is 0. READ. A client MUST check both.

R19. [`WheelMove`](../../docs/control/events/WheelMove.md): `start`, `complete`, `fail`, plus
`position`. [`WheelSlotNum`](../../docs/control/events/WheelSlotNum.md) carries a `slots`
array at slot discovery. READ.

### Names and settings

R20. [`get_wheel_slot_name`](../../docs/control/methods/get_wheel_slot_name.md) returns a
string array in ascending slot-id order. [`set_wheel_slot_name`](../../docs/control/methods/set_wheel_slot_name.md) takes
an array of strings: each bad element gives 105 without stopping, so the reply can contain
duplicate `error` members; 209 on a size mismatch; 318 closed; persisted. READ.

R21. [`get_wheel_setting`](../../docs/control/methods/get_wheel_setting.md) returns
`{names, exp_sec}`. [`set_wheel_setting`](../../docs/control/methods/set_wheel_setting.md)
takes `{names?, exp_sec?}`: 107, 105, 108, 318, 209. A member of the wrong type is ignored, so
`{}` succeeds. The first failure stops processing; earlier changes are kept and persisted (no
rollback). READ.

R22. [`set_wheel_unidirection`](../../docs/control/methods/set_wheel_unidirection.md) and
[`calibrate_wheel`](../../docs/control/methods/calibrate_wheel.md) always fail (318, 203, or
usually 210; `set_wheel_unidirection` also 106 for malformed input). No motion happens. READ. A client MUST NOT offer them as working functions.

### Factory names, the dark slot and automatic moves

R22a. When no slot names have been saved, the names are `dark` for slot 0, `IRCUT` for slot 1
and `LP` for slot 2. Saved names (R20, R21) replace them. READ. Slot 1 is the IR-cut filter
used for ordinary imaging, slot 2 the light-pollution filter, slot 0 the dark (closed)
position: READ for the fixed slot numbers that calibration and goto use (R22d); the optical
role is INFERRED from the names. Calibration log text uses a fixed copy of the three default
names, whatever names the user saved. READ.

R22b. The FITS `FILTER` keyword holds the name (saved or default) of the slot the wheel is at
when the header is built. While the wheel is moving the name is empty and the keyword is left
out; without a wheel there is no `FILTER`. READ. A client MUST NOT assume `FILTER` names the slot
that the capture was requested with.

R22c. A "dark filter" in this specification is a slot whose name equals `dark`, ignoring case.
The test uses the name, not the slot number: renaming slot 0 makes it count as non-dark, and
naming another slot `dark` makes that slot count as dark. Without a wheel no slot is dark.
READ. In a capture run (sequence or plan), an entry counts as a light frame only when its frame
type is light and its `filter` slot is not dark. Entries that are not light frames skip
dithering, guiding, the autofocus triggers of R14, the after-flip autofocus and the
below-horizon check, and do not count toward target progress. READ.

R22d. The firmware moves the wheel by itself in the cases below (both builds: the 32-bit build
has the same set of wheel-moving callers with the same targets, and its start-up row commands
slot 1 directly). "Restored" means it returns to the slot it was at before. Nothing else moves
the wheel. READ unless the row says otherwise.

| Trigger | Condition | Target | Restored |
|---|---|---|---|
| device start-up, or `open_wheel` (R16) | a wheel is found | toward 1 | no |
| any goto with plate solve ([`AutoGoto`](../../docs/control/events/AutoGoto.md)), including `iscope_start_view` with a target and each ViewPlan target | wheel fitted and not already at 1 | 1 | on failure, yes. On success, yes, unless a ViewPlan is running or `stack.auto_lenhance` is true; then slot 2 if the target's `lp_filter` is true, otherwise it stays at 1 |
| star-mode view start, including the View worker relaunch by `iscope_start_stack` ([stacking.md R6b](stacking.md)) | a slot was saved (below) and differs from the current one; the move finishes before the view's first frame (R22g) | the saved slot (0 is never saved, so a wheel set to 0 returns to the last saved 1 or 2; OBSERVED 2026-10-16 for a stack start on an S50 Pro) | not applicable |
| a view stops or a new view replaces it | current slot is 1 or 2 | none; the slot is saved persistently for the next star-mode view | not applicable |
| `set_setting {stack_lenhance}` | wheel open and idle | 2 for true, 1 for false | no; the value is not stored separately (`get_setting` derives `stack_lenhance` from the position) |
| capture run (sequence or plan) entry | `filter` within the slot range and different from the current slot | the entry's `filter` | no; `af_wheel_change` then triggers autofocus (R14) |
| live stack in photometry mode | the photometry reference loads and a wheel is fitted | 1 | yes, when the stack ends |
| autofocus | not factory mode, current slot 2, and an internal gate whose meaning was not identified | 1 | yes, when autofocus ends |
| three-point polar alignment | an internal option of the run is set | 1 | yes |
| live video (RTMP) start | the video page opens | 1 | no |
| bias and flat creation, manual or automatic ([calibration-frames.md](calibration-frames.md)) | current slot differs | bias 0, IR flat 1, LP flat 2 | yes, also on failure |
| dark and hot-pixel creation (`start_create_dark`, `start_create_hpc`, automatic master dark) | wheel fitted | 0 | yes ([calibration-frames.md](calibration-frames.md)) |

Which view modes open the live-video page (and so take the RTMP row) is INFERRED: the page is
selected on a non-star branch of view start, not traced per mode.

Firmware 9.75: master dark creation has an abort path. If moving the wheel
to slot 0 fails and the stop flag is set, the result is 253; an early return with 253 also
occurs when no wheel position was captured. READ (64-bit).

R22e. Parking or closing the arm does not move or reset the wheel. The device's park and
move-to-horizon commands, and the imager's go-home step after a ViewPlan or a capture run with
`park_mount`, issue no wheel command; the imager does not react to the park or horizon events
or to the mount-closed state with any wheel action. READ. Neither `start_exposure` nor
`iscope_start_stack` checks whether the mount is parked or the arm is closed when it starts, and
neither takes any wheel action over park, horizon or mount-closed state. READ (their handlers and
synchronous callees). The live stack a stack start launches does, once running, stop itself when
the mount reports not tracking below the horizon or over the altitude limit (R22l,
[stacking R6c](stacking.md#live-stack)). The guider's `scope_park` refuses while a ViewPlan is
running. READ (64-bit guider).

R22l. The running live stack is the only capture path that halts on a below-horizon or
altitude-limit condition. It reads the mount's tracking state through the guider at start-up and
again on every stacking pass; when the reply reports not tracking with reason `below horizon`
(270) or `alt exceed limit` (527), the worker quits and saves no further frame. Single and
continuous `start_exposure` captures and the legacy sequence capture make no such test; only the
ViewPlan and autosave-plan light-frame capture check a computed altitude instead, and that check
is skipped for dark or non-light frames. READ (both builds). Details:
[stacking R6c](stacking.md#live-stack) and
[tracking-park-and-state R36a](mount-and-motion/tracking-park-and-state.md#park-home-and-the-arm).

R22f. A client that needs a particular slot for a capture SHOULD set it with
`set_wheel_position` after any goto, view start, stack start or calibration has finished, and SHOULD read
`get_wheel_position` (or `FILTER`) rather than assuming the slot it last requested. INFERRED.

R22g. When a stack start relaunches the View worker. `iscope_start_stack` and `start_stack` ask
for view stage 3 (Stack). READ.

- **Reuse.** If the View worker is running and its current stage is already Stack, the request
  reuses it. Nothing is relaunched and the wheel is not touched. `iscope_start_stack
  {restart:true}` in that state is refused with 259 ([stacking.md](stacking.md#interactions)).
- **Relaunch.** In every other case the request relaunches the worker. That covers no worker
  running, or a worker running another stage, including a Stack stage that has been stopped.
  1. With the camera closed it fails with 318.
  2. Otherwise it stops the current view. Stopping a star-mode view saves the current slot when
     it is 1 or 2 (R22h).
  3. It starts the worker in star mode.

The relaunched worker does the following before its first frame, in this order. READ.

1. Restore the saved star-view slot.
2. Set the gain.
3. Start sidereal tracking.
4. For the Stack stage: the temperature-triggered autofocus check, then automatic exposure, then
   the stack loop. The 32-bit build has no automatic-exposure step here
   ([stacking.md R6e](stacking.md#sequence)); steps 1 to 3 and the conditions below match on
   both builds.

Step 1 runs only when a wheel is fitted, and it does nothing in any of these cases:

- no slot has been saved;
- the saved value is not 1 or 2;
- the wheel position cannot be read;
- the wheel is already at the saved slot.

Otherwise it moves the wheel and waits for the move to finish before step 2. If the wheel is
already moving (203), the move is skipped and the start continues. READ.

A stack start therefore moves no wheel only when it reuses a running Stack stage, when no wheel
is fitted, when no valid slot is saved, or when the wheel is already at the saved slot. When
the relaunch stops a star-mode view with the wheel at 1 or 2, that slot is saved and then
restored onto itself, so nothing moves. A wheel left at 0 (or any slot other than 1 or 2) is
moved to the last saved 1 or 2. READ.

R22h. The saved star-view slot is a persistent device setting, not a wire field. It is written
only when a star-mode view stops or is replaced while the wheel is at 1 or 2; no other slot is
ever written. The star-mode start of R22g is its only reader. No method reads, writes or clears
it. Start-up does not reset it, so it survives restarts. No setting or parameter suppresses the
restore. READ. A client therefore cannot keep a stack start from moving a wheel set to 0, except
through the conditions in R22g.

R22i. Wheel moves while a live stack or an exposure runs. Inside a running live stack, only
three things move the wheel. READ.

- Autofocus started from inside the stack by its temperature trigger, under the conditions of
  R22d, restored afterwards.
- Photometry mode: to 1, restored when the stack ends.
- The centring goto after the stack's first successful plate solve, when the target is farther
  off than the centring threshold: to 1 and restored, except as in the goto row of R22d.

Dithering, frame saving and automatic exposure contain no wheel command. READ. Frames at the
dark slot are not expected to plate-solve, so that goto, and its wheel move, would not happen.
INFERRED.

Single (mode 0) and continuous (mode 1) exposures contain no wheel command. READ.

From outside, these can move the wheel during a stack or exposure. READ.

- `set_wheel_position`.
- `set_setting {stack_lenhance}`.
- Any new view or stage start. It stops the stack and runs R22g.
- Calibration-frame creation.
- A capture-run entry.
- Live video start.
- Three-point polar alignment.

The list of firmware callers that move the wheel is complete for this build. The stack's own
mount moves do not reach a wheel command: the mosaic tile goto is a plain mount goto, the
stack's small corrective moves are fine mount moves, and dithering only sends a command to the
guider. READ. A capture run (R20a in
[legacy plans and sequences](legacy-plans-and-sequences/sequences.md#capture-run-frames)) recentres and does a meridian flip
through the same goto worker as the stack's centring goto. That worker moves the wheel to 1 and
restores it, under the conditions in the goto row of R22d. READ (both builds).

R22j. Capture runs and the dark slot. A capture-run entry whose `filter` is the dark slot is
still captured and saved. The run moves the wheel to the slot before every frame, waits for the
move, and never restores it. It treats the entry as a non-light frame: no dithering or guiding,
no meridian flip or recentring, no autofocus, no annotation, no below-horizon check (plan runs),
and no count toward target progress
([legacy-plans-and-sequences R20a](legacy-plans-and-sequences/sequences.md#capture-run-frames)). READ.
The FITS `IMAGETYP` follows the entry's `type`, not the slot. A `light` entry at the dark slot
therefore says `Light`. READ.

R22k. Nothing refuses or alters a capture because the wheel is at the dark slot. Neither the
dark-slot test nor the frame type rejects a capture or a stack, and neither changes the exposure,
gain or calibration. Their only effects are the skips in R22c and R22j. The live stacker, single
and continuous exposures, and `start_exposure {type:"dark"}` do not test the slot at all.
`type` only labels the frame
([legacy-plans-and-sequences R20c](legacy-plans-and-sequences/sequences.md#capture-run-frames)).
READ (every caller of the dark-slot test, both builds).

## Interactions

| Action | Effect |
|---|---|
| `start_auto_focuse` (stage form) | stops the current view stage |
| full `iscope_stop_view` | may close the focuser |
| `start_create_hpc` | moves the wheel to 0, then tries to restore it |
| goto, view start, `set_setting {stack_lenhance}`, capture-run entries, photometry stack, autofocus, 3PPA, live video, bias/flat creation | move the wheel by themselves (R22d); a filter change between stack runs clears the live stack ([stacking.md](stacking.md)) |
| `iscope_start_stack` / `start_stack` when the Stack stage is not already running | relaunch the View worker, which restores the saved star-view slot before the first frame (R22g, R22h) |
| capture-run entry at the dark slot | captured and saved; dithering, guiding, flip, recentring and autofocus skipped; no refusal (R22j, R22k) |
| `scope_park` / `scope_move_to_horizon`, mount closed | no wheel action; `start_exposure` and `iscope_start_stack` take no wheel action and do not gate at start, but a running live stack quits below horizon or over the altitude limit (R22e, R22l) |
| `start_create_dark` / calibration on wheel models | require an open wheel (318) |
| wheel moving | `set_wheel_position` 203 |
| AF running | second `start_auto_focuse` 268 |

## Errors

Chapter codes: 104, 105, 106, 107, 108, 109, 201, 202, 203, 204, 207, 209, 210, 236, 268, 300, 318.

## Not covered or unresolved

- `backlash` on the 32-bit build.
- Focuser step unit and its relation to `max_step_range`.
- What separates `AutoFocus` `status_flag` 2 from 3.
- Wheel slot count beyond positions 0..2 accepted by `set_wheel_position`.
- The internal gate that lets autofocus move the wheel from slot 2 to slot 1 (R22d), and which
  option enables the move in three-point polar alignment.
- Which view modes start live video and so set slot 1 (R22d).

## Appendix: Validating on a live device (non-normative)

1. `open_focuser`; time the reply. `move_focuser {"step":N,"ret_step":true}`; count
   `FocuserMove complete` events.
2. `start_auto_focuse` twice; expect 268 on the second.
3. On a wheel model, `set_wheel_position [2]` then immediately `[1]`; expect 203.
