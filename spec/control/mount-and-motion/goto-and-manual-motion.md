# Goto, manual motion and sync

Part of the [mount and motion chapter](../mount-and-motion.md). This file covers raw and solved
goto, joystick, fine and angle moves, the movement-permission flag, and sync. Labels, basis and
the routing of calls between imager and guider: [mount-and-motion.md](../mount-and-motion.md): [Conventions](../mount-and-motion.md#conventions), [Where a call is executed](../mount-and-motion.md#where-a-call-is-executed) and [Common rules for guider calls](../mount-and-motion.md#common-rules-for-guider-calls).

## Goto

Two layers exist:

- **`scope_goto`** (guider): a raw slew to RA/Dec. No plate solving.
- **`start_auto_goto`** (imager): a goto worker named `AutoGoto`. It slews, then may expose,
  plate-solve, refine and focus. Its child steps report as their own events. READ.

### Raw slew: scope_goto

R13. Preconditions: a connected, slew-capable mount (315, 210); a movement state that admits a
new goto (203 otherwise). No parked-state or altitude check in the handler. READ.

R14. On acceptance the driver sets the target, sends the slew command, reads the controller's
acceptance and starts a movement-watcher worker. The reply follows the acceptance; it does not
wait for arrival. READ. The watcher may turn tracking on at arrival. READ.

R15. Progress is reported by the [`ScopeGoto`](../../../docs/control/events/ScopeGoto.md) function event (states `working`, then
`complete`, `fail` or `cancel`) and, through tracking checks, [`ScopeTrack`](../../../docs/guider/events/ScopeTrack.md). Either may
reach the client before the reply: the order is a race. READ (firmware 9.31 64-bit, 9.75 64-bit and
32-bit). The watcher is a new thread that emits `ScopeGoto` `working` as its first action, before
it polls the mount, and nothing makes it wait for the reply. The handler builds and writes the reply
only after the watcher has started. Events and replies are written straight to the socket under the
same per-connection write lock, with no shared output queue, so bytes go out in whichever order the
threads take that lock. At 4700 the imager forwards guider events from its relay-reader thread as
they arrive, while a different thread writes the relayed reply, so even a guider-side order is not
preserved. This is a property of the code, not a measured frequency. A client MUST NOT assume the
reply arrives before the first event, and MUST accept `ScopeGoto` `working` before the reply (see
[liveness-and-ordering R47](../session-handshake/liveness-and-ordering.md#ordering)).

```text
client            imager:4700            guider:4400             mount
  |-- scope_goto ---->|                       |                     |
  |                   |-- (103) relay ------->|                     |
  |                   |                       |-- target + slew --->|
  |                   |                       |<-- accepted --------|
  |                   |<-- result 0 ----------|  start watcher      |
  |<-- result 0 ------|                       |                     |
  |<== ScopeGoto working (forwarded) =========|   (may precede the reply: race)
  |<== ScopeTrack ... ========================|                     |
  |<== ScopeGoto complete | fail | cancel ====|                     |
```

R16. [`scope_abort_slew`][sab] needs a connected mount (315). It sends the controller's general
stop command and always replies 0, even if the write fails. READ. It does not stop the guider's
own movement workers (the goto, home and horizon watcher, speed-move repeat, move-by-angle), so a running
worker may command motion again or report its own terminal event. READ. Which motions the
controller halts, and the final mechanical stop, are unresolved (needs a device test). To end a
watcher-driven goto, home or horizon move, a client SHOULD also send [`scope_move`][smv]
`["none"]` (R38a).

R17. [`can_goto`][cg] returns a boolean from cached state only (connected flag and a worker
state). It is INFERRED to predict whether `scope_goto` would be accepted. A client SHOULD still
handle 203/315 from `scope_goto`. [`scope_is_moving`][sim] (connected mount, else 315) returns
one of `none`, `ScopeGoto`, `ScopeHome`, `ScopeMoveToHorizon`, `move_home_horizon`,
`clear_backlash` or `move`. While a guider movement worker runs, the value names that worker's
move type (manual and angle moves report `move`). Otherwise it is the controller's own report.
READ. A client MUST treat any value other than `none` as moving.

### Solved goto: start_auto_goto

R18. `start_auto_goto` takes `{ra, dec}` or `[ra, dec]`. Checks, in order. READ:

1. a View function is active (view mode nonzero): 210, before parsing;
2. missing or non-number coordinates: 108;
3. goto worker already running: 268;
4. a coordinate within 0.1 of the sentinel -999: 209;
5. computed altitude at or below the horizon: 270 `below horizon`;
6. the mount cannot goto now: 210. This reflects the mount's state, not the target. READ.

The horizon check uses the device's stored location and clock, and can refresh the location
cache even when the call then fails. READ.

R19. Code 0 means the [`AutoGoto`](../../../docs/control/events/AutoGoto.md) worker started. Mount, exposure and solver failures arrive
later as `AutoGoto` events (F states plus `count`, `hint`, `target_name`, `target_ra_dec`, and
legacy direct states `start`/`working`/`delay`/`complete`/`fail`) and [`AutoGotoStep`](../../../docs/control/events/AutoGotoStep.md) (`fail`
with `code`). READ. The legacy direct `AutoGoto` event always carries `page` and `func`, and
`tag` when non-empty. Its `state` is one of `start`, `working`, `delay`, `complete`, `fail`.
`start` adds `target_ra_dec` (only when the RA is not the -999 sentinel) and `target_name` (only
when non-empty); `working` adds `count`. Any state adds `error` and `code` when the worker passes
a non-zero error code. READ. The F-path `AutoGoto` event carries the common F members plus
`hint`, `target_name` and `target_ra_dec`. READ. No further members are known; the union in the
event card is complete. INFERRED. Child `ScopeGoto` events from
the imager's nested goto carry `cur_ra_dec` and `dist_deg` (distance in degrees, INFERRED);
guider-origin `ScopeGoto` events instead may carry `close` (boolean). READ.

R20. [`start_auto_goto_pixel`][sagp] uses the same worker with a pixel target `{x, y}`. It
has no View-mode gate, but the sentinel, horizon and reachability checks still run on the raw
pixel numbers before any solve. READ. The horizon check on pixel values looks like a firmware
quirk (INFERRED); a valid pixel request can be refused with 270. In a pixel goto the worker first
plate-solves the current live frame. It hands the `{x, y}` point to the solver and uses the
solved sky position as the goto target. READ. `x`, `y` are coordinates in the full live-camera
frame used for solving. INFERRED. Their origin and axis direction are unresolved. The app 3.3.2
never sends `start_auto_goto_pixel`, because its tap-to-centre uses `start_func` `GoPixel` (R22a),
so the app does not settle them. READ (app 3.3.2, bounded search).

R21. [`stop_auto_goto`][stag] sets the capture error to 253 `aborted` when the capture state
allows, then stops the worker. It can block until the worker exits (no deadline established)
and always replies success. READ.

R22. `start_func` with `name` `GoPixel` starts the imager's centring worker, which moves the
mount to bring a displayed pixel to the centre. It is refused (203) while the mount is
occupied. See [`start_func`][sf]. READ.

R22a. The app 3.3.2 sends `start_func` `{name:"GoPixel", x, y}` when the user taps the live
wide-camera view. It does not send it while the telescope view is shown, during autofocus or
while a goto is running. The app converts the tap through the inverse of the view's zoom and pan
and undoes any 90° display rotation. It then scales the point to the stream's native resolution:
`rtsp_width`/`rtsp_height` from the wide camera's `get_setting` preview block when they are
positive, else the decoded video's own size. It sends the result truncated to integers, and only
when the point lies inside the frame. `x` and `y` are therefore pixels of the unrotated wide
RTSP frame, with the origin at the top-left, `x` increasing to the right and `y` increasing
downward. READ (app 3.3.2). That the device reads them in the same frame is INFERRED. The app
has no code that sends `stop_func` `GoPixel`. READ (app 3.3.2, bounded search).

## Manual motion

### Joystick moves: scope_speed_move

R23. [`scope_speed_move`][ssm] takes a named object. READ:

- `percent` (or a direct `speed` in native units, which wins if present);
- `level` (integer): > 0 selects the fast scale, base speed `1440*percent/100`; <= 0 selects
  the slow scale, `64*percent/100`, multiplied by the stored speed-move ratio when that exceeds
  0.01;
- `angle` (integer degrees): axis speeds are `cos(angle)*speed` and `sin(angle)*speed`. The zero
  direction and sense relative to the sky are unresolved;
- `dur_sec` (integer): passed to the controller's timed-move field (seconds INFERRED). The app
  sends 3.

R24. A move starts or updates one repeat worker and replies once it is started. Repeated
requests update the same shared parameters. READ. A client implementing a joystick SHOULD
re-send the move while the control is held, at an interval below `dur_sec`, so the timed move
does not lapse (INFERRED from the timed-move field; the app's re-send interval is not
established).

R25. Stop: send `percent` below 0.01 (for example 0). The device then sends zero speeds on both
axes and polls for up to about 1000 ms before replying. READ. A client MUST send an explicit stop
when the control is released.

R26. Per-axis speeds above 1440 in magnitude are clamped to 1440; the repeat worker snaps
900..1000 to 899 or 1001 (anti-resonance). READ. No completion event exists. READ.

R26a. When the controller reports an axis limit during a speed move, a guider worker asks the
imager to play a warning sound and emits a guider [`Alert`](../../../docs/control/events/Alert.md)
event with `code` 532 (upper limit), 533 (lower limit), 540 or 541 (both with the generic text
`fail to operate`). It then waits about 3 s before checking again. READ. The limit geometry is
controller-defined. INFERRED. A client SHOULD stop a speed move when it receives one of these
alerts.

R27. [`speed_move_ratio`][smr] sets the slow-scale ratio from per-camera pixel scales
(`cam_id`, `pix_scale`, `sel_wide_cam`). `sel_wide_cam` false sets the ratio to -1 (disabled).
The new `pix_scale` is stored before later checks, so a failed call (300) can leave it changed.
READ. The imager sends this itself on guider reconnect (R5).

### Fine and angle moves

R28. [`scope_fine_move`][sfm] takes `speed` `[x, y]`, optional `limit` (default true: clamp to
±16), `dur_sec` (default 1, divisor) and `backlash_comp`. The x speed may be altitude-compensated
(cosine factor). The handler **waits for the mount to stop** before replying, so the reply
follows the motion. READ. The speed values are passed to the controller as its native rate
value (after the `dur_sec` division, the optional ±16 clamp and the 1440 clamp), with no
conversion in the guider. READ. They share the number space of `scope_speed_move` speeds (R26).
The physical unit is unresolved (needs a device test).

R29. [`scope_move_left_by_angle`][sml] starts a [`MoveByAngle`](../../../docs/guider/events/MoveByAngle.md) worker. Reply 0 means accepted. Progress: `MoveByAngle`
events with `state` `start`, `moving` (with `value`, degrees INFERRED), `complete` or `fail`.
No `error`/`code` members. READ. With a connected mount, `degree` (integer, `{degree}` or
`[degree]`) is required: missing or non-integer gives 104, after the 203 (moving) and 210 (no
motion capability) checks. READ. Without a connected mount, `degree` is ignored. The call replies
315, unless `manual` is the string `manual`, in which case it emits `MoveByAngle` `complete` at
once and replies 0. READ. That this is a test or simulation hook is INFERRED.

### The movement-permission flag

R30. [`not_move`][nm] sets an internal flag to 0 and [`can_move`][cm] sets it to 1. Neither
moves or stops the mount, and neither is a getter. READ. The flag gates one thing: when the
stack mode is set to wide timelapse, the imager stops mount tracking only if the flag is 1. With
the flag at 0 it keeps tracking. READ. That 0 means "a main stack is still running" is INFERRED.
The flag does not gate goto, manual motion or any other handler. READ. A client MUST NOT use
them as a stop command.

## Sync

R31. [`scope_sync`][ss] `{ra, dec}`: the guider always stores the pair as its fallback
coordinates. With a connected, sync-capable mount it also sends the sync to the controller and,
on success, records the pair for recovery. It does not slew. READ. Success is returned even
when no mount is connected (only the fallback changed). A client MUST NOT read success as proof
that the mount model changed. The Android app sends RA already divided by 15 (hours). READ.

In the checked 64-bit and 32-bit builds of firmware 9.75, the imager suppresses the compass-calibration prompt after a waited sync reply passes its textual success test. Compass state then reports cali as 0 even if the sensor's underlying calibration-needed flag remains set. The suppression marker does not rewrite the stored fit. In the checked 64-bit 9.75 path, calibration processing clears suppression, successful fit/commit sets it again after requesting clear-azimuth, and the detected-movement path clears it again. The checked 64-bit 9.31 packer reports the underlying flag directly. READ. Physical calibration, detection of every movement and full 32-bit movement-detector parity remain unresolved. The guider's mount handlers (goto, park, speed move, sync, move, tracking, position,
state, equatorial mode, abort, fine move) are identical to 9.31 apart from compiler noise. READ.
In the checked 64-bit and 32-bit builds, firmware 9.31 manual round movement uses westward nine-second movement requests and a 180-second budget. Firmware 9.75 uses a 90-second manual budget; its automatic calibration selects a direction from the current axle angle and uses 65 seconds. These paths request slew-rate index 7 and use finite wrapped displacement of at least 15 degrees to arm completion, followed by displacement at most 5 degrees to finish the round. Their movement cleanup requests stop. In firmware 9.75, internal flags select immediate manual failure notification or recording of the first eligible nonzero automatic failure while the calibration session remains active; they add no public request member. Movement-request transport failure and replies lacking the success marker have distinct failure routes, and stop-request failures are logged without a new code assignment there. READ. Stop delivery, physical travel and controller-limit behavior remain unresolved.

R32. [`scope_sync_planet`][ssp] takes no params. It works only in view mode 2 (Moon) or 3 (Sun),
else 300. The imager computes the body's position (the Moon path can refresh the stored
location), divides the RA by 15 and sends `scope_sync` `[ra, dec]` to the guider, waiting up to
10000 ms for one attempt. READ. That the RA is then in hours is INFERRED. The call changes the
mount alignment. Errors: 241 (request not sent), 502 `mount sync failed`
(bad, absent, sentinel or 207 reply), or the guider's code passed through.

[sagp]: ../../../docs/control/methods/start_auto_goto_pixel.md
[stag]: ../../../docs/control/methods/stop_auto_goto.md
[sf]: ../../../docs/control/methods/start_func.md
[nm]: ../../../docs/control/methods/not_move.md
[cm]: ../../../docs/control/methods/can_move.md
[ssp]: ../../../docs/control/methods/scope_sync_planet.md
[sab]: ../../../docs/guider/methods/scope_abort_slew.md
[cg]: ../../../docs/guider/methods/can_goto.md
[sim]: ../../../docs/guider/methods/scope_is_moving.md
[ssm]: ../../../docs/guider/methods/scope_speed_move.md
[sfm]: ../../../docs/guider/methods/scope_fine_move.md
[sml]: ../../../docs/guider/methods/scope_move_left_by_angle.md
[smv]: ../../../docs/guider/methods/scope_move.md
[smr]: ../../../docs/guider/methods/speed_move_ratio.md
[ss]: ../../../docs/guider/methods/scope_sync.md
