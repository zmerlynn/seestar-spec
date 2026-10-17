# Tracking, park, mount mode and motion events

Part of the [mount and motion chapter](../mount-and-motion.md). This file covers tracking, park,
home and the arm, equatorial mode, position and connection state, the meridian-flip settings and
the events that report motion. Labels, basis and the routing of calls between imager and guider:
[mount-and-motion.md](../mount-and-motion.md): [Conventions](../mount-and-motion.md#conventions), [Where a call is executed](../mount-and-motion.md#where-a-call-is-executed) and [Common rules for guider calls](../mount-and-motion.md#common-rules-for-guider-calls).

## Tracking

R33. [`scope_set_track_state`][sts] takes a boolean: bare `true`, `[true]` or
`{"tracking": true}`. The app sends a bare boolean. READ. The driver sends the track-on or
track-off command and checks the acknowledgement. Whether or not that worked, the handler then
forces a tracking-state check, which can emit `ScopeTrack`. The event can precede the reply.
READ.

R34. `ScopeTrack` (guider origin, forwarded): `state` `on`/`off`, `tracking` (boolean),
`manual` (boolean: transition caused by a manual command, INFERRED from name), optional `route`,
and `error`/`code` only for a positive fault code. READ. It is also emitted by goto arrival
and by position reads that notice a change (R15, R42). READ. A client SHOULD treat
`ScopeTrack` as the authority on tracking state, not the reply to `scope_set_track_state`.

R34a. When `ScopeTrack` is sent, and what its codes mean. The guider remembers the last tracking
flag and code it reported and emits `ScopeTrack` only when one of them changes; there is no
periodic tracking timer that emits it. The emission therefore rides on whatever reads the
tracking state: the forced check after `scope_set_track_state` (R33), `scope_get_track_state`
(R35), the coordinate and state reads (`scope_get_ra_dec`, `scope_get_state` and the device-state
poll, R42, R43), goto arrival, and the imager's focus and position polling. The fault `code` when
not tracking is the mount controller's tracking-reason reply, mapped by the guider: `below
horizon` (270), `alt exceed limit` (527), other mapped controller reasons, 203 while a home or
horizon move is in progress, or the generic `fail to operate` (207) for any reply the guider does
not recognise. READ (64-bit). The `below horizon` decision is the controller's, not a guider
altitude computation. READ. The interval that sets how soon a reader sees a changed state is the
client's or imager's poll rate, and is INFERRED.

R35. [`scope_get_track_state`][sgt] is registered in the guider (R8). The app and the imager
send it with no params and treat the result as a boolean; the imager also looks for a
`track_code` member when not tracking. READ (consumers). The guider replies with a boolean
(tracking), or `{"value": <bool>}` if `ret_obj` is true. When not tracking, the reply also has
`track_error` (string) and `track_code` (integer). Errors: 315 (no mount), 210 (no tracking
control), or the driver's error code. READ. The call may also emit `ScopeTrack` if the state
changed since the last event. READ. A client SHOULD still prefer `ScopeTrack` (R34).

## Park, home and the arm

The Seestar's optical tube folds down ("arm closed") when parked and raises ("arm open") for
use. The app maps its arm controls to these calls. READ (app):

| App action | Method sent |
|---|---|
| Arm close / park | [`scope_park`][sp] (no params) |
| Park and switch mount mode | [`scope_park`][sp] `{"equ_mode": <bool>}` |
| Arm open | [`scope_move_to_horizon`][smh] (no params) |
| Cancel arm motion | [`scope_move`][smv] `["none"]` (R38a) |

R36. `scope_park` requires a connected, home-capable mount (315, 210). If `equ_mode` parses,
the guider first asks the imager whether a ViewPlan is running and fails with 536 if so;
omitting `equ_mode` skips that check. The driver sends the home command, records the requested
mode, starts the movement watcher and replies on acceptance. A busy watcher gives 203. READ.

R36a. Park and the below-horizon event. `scope_park` sends the home command and starts its
movement watcher; it sends no tracking-off itself, and the watcher polls only mount status, not
the tracking reason. A `ScopeTrack` off with `below horizon` (270) is therefore not produced by
the park routine. It appears when a reader next samples the tracking state and the controller
then reports the arm below the horizon (R34a). When the imager sees a forwarded `ScopeTrack` off
that is not a manual transition and carries 270 or 527, it raises an `Alert` with that code (and
`wide_cam`); a running live stack also quits on 270 or 527
([stacking R6c](../stacking.md#live-stack)). READ (64-bit). OBSERVED 2026-10-16 (S50 Pro,
firmware 9.31): in one park with a view running, `ScopeTrack` off `below horizon` 270 arrived
about 5 s into the descent; in a second park with no view running, it arrived about 14 s after
the park completed, with the view already stopped. That the latency is the reader's poll interval
is INFERRED.

R37. `ScopeHome` (function event, guider origin, forwarded) reports `working` then a terminal
state. Every `ScopeHome` event carries `close` (boolean) when the guider can read the axle
position. `close` is true when the arm is folded (first axle at or below about -85). READ. That
the unit is degrees and the first axle is elevation is INFERRED. `equ_mode` (boolean) appears
only on `complete`, when a mode was requested. READ. A client SHOULD use `close` on the terminal
event to confirm the arm state. After the move the watcher may change the
mount mode to the requested one. READ. A client MUST wait for a terminal `ScopeHome` before
assuming the arm is closed or the mode switched.

R38. [`scope_move_to_horizon`][smh] (MUTATOR / established, tier C) reads no params. It fails with
203 when the mount is moving and 210 when the driver cannot do motion. On a missing or disconnected
mount the reply has neither `result` nor `error` (an envelope with `id` only). READ. A client MUST
treat such a reply as a failure (no mount). On success it stores movement type 5, starts the
horizon-movement worker and replies 0 (worker launched). READ. The worker commands motion, then
polls the axle coordinates every 0.5 s with a 30 s deadline, ending successfully when the first axle
coordinate is 0 or above; on that normal path it then commands a stop and waits for the mount to
stop. READ. Failures (320, 500, 204 timeout) arrive only as `ScopeMoveToHorizon` F events
(`working`, `complete`, `fail`, `cancel`, plus `close` (R37) when the axle position can be read).
READ. Because motion is commanded before the coordinate test, repeating the call with the arm
already up can still move the mount briefly. READ. A client SHOULD treat a terminal `complete` as
"arm open" (INFERRED: the first axle is elevation on alt-azimuth hardware). The axle-to-sky relation
in equatorial mode and the stopping distance are unresolved (needs a device test). The app's
arm-cancel control sends [`scope_move`][smv] `["none"]`, which stops the horizon move (R38a).
[`scope_abort_slew`][sab] (R16) does not stop the guider's worker.

R38a. [`scope_move`][smv] takes `direction` (`north`, `south`, `east`, `west`, `none`) and
optional `duration_sec` (integer 1..9), positional or keyed. Errors: 315, 210, 105 (direction not
a string), 209 (unknown direction), 104/204 (bad duration), 203 (a direction move while a
goto, home or horizon move runs). `none` during a goto, home or horizon move stops the mount, waits up
to about 5 s, ends the guider's movement worker and replies 0. Otherwise `none` just commands a
stop. READ. That the NONE motion is a controller stop is INFERRED. The cancelled worker reports
its terminal event. A client MAY use `["none"]` to cancel arm motion.

R38b. `ScopeTrack` with `fail to operate` (207) during a horizon move. While the arm is moving to
the horizon the mount is not tracking, and a tracking-state read taken during the move can report
off with code 207. 207 is the guider's default tracking reason for a controller reply it does not
recognise as a known state (R34a); here it means only that tracking is off, with no specific
reason, during the move. It is benign and needs no client action. READ (64-bit). That the
controller's reply is unrecognised specifically because the move is in progress is INFERRED.

R39. No guider handler or driver goto path checks "parked" or the arm position before moving.
Goto checks only connection, capability and busy state. READ. The controller's behaviour when
told to move while folded is unresolved (needs a device test). A client SHOULD open the arm (R38)
and wait for its terminal event before goto or manual moves.

## Equatorial mode

The mount runs in alt-azimuth mode by default or in equatorial mode (`equ_mode` true), for
example on a wedge. READ (flag); INFERRED (physical setup).

R40. [`scope_set_eq_mode`][seq] takes `{equ_mode}` or `[equ_mode]` (boolean or integer;
missing or wrong type gives 106) and needs a connected mount (315). The mount must be at its home
(folded) position: otherwise the call fails with 254 and nothing is sent. READ. That the
controller's status flag tested here means "at home" is INFERRED. The guider then sends the
controller's equatorial or alt-azimuth mode command, re-applies the stored site location for the
new mode, and replies 0. A failed mode write gives an error without a specific code. READ.
`MountMode` with `equ_mode` (boolean) is emitted only after a successful mode write. READ. A
client SHOULD park (R36) before switching mode, or use `scope_park` with `equ_mode`.

R41. The mode affects other features: `scope_park` can switch it (R36); polar alignment chooses
`EqModePA` in equatorial mode and `check_pa_alt` checks the location only in equatorial mode
(see [polar-alignment.md](../polar-alignment.md)). READ. `MountMode` is the event to follow; the
imager also consumes it internally. READ.

## Position and connection state

R42. [`scope_get_ra_dec`][srd] reads live coordinates from a connected mount, else returns the
cached pair from the last sync, else 207. A failed live read counts failures; after repeated
failures the guider may ask the imager whether autosave is running and stop capture, mark the
mount disconnected (event `AutoCloseMount`, no members) or run a communication-failure handler.
READ. A client SHOULD NOT poll this getter at high rates; it has recovery side effects.

R43. [`scope_get_state`][sgs] (no params) returns `alt` and `az` (degrees, from the controller's
horizontal position) and `ra` (hours) and `dec` (degrees) from the controller. READ. The units
are INFERRED. The guider passes `ra` and `dec` through as the controller reports them, with no
precession or epoch conversion. READ. Which epoch the controller reports (J2000 or of date) is
not determined by the device firmware. unresolved. Errors: 315, 210, or a read error. If only the equatorial
read fails, the reply carries both an error and a partial result with `alt`/`az`. READ. A client
MUST check for `error` first. The app also reads position with [`scope_get_equ_coord`][sge] (no
params; it expects an RA in hours and a Dec) and [`scope_get_horiz_coord`][sgh]
(`{"ret_obj": true}`; it expects `alt_az`), and reads or sets backlash through the raw controller
pass-through [`scope_send_cmd`][ssc]. READ (app). `scope_get_equ_coord` returns `{ra, dec}`
through the same reader and side effects as `scope_get_ra_dec` (R42). `scope_get_horiz_coord`
returns `[alt, az]`, or `{"alt_az": [...]}` with `ret_obj` (315, 210). `scope_send_cmd` takes
`cmd` (string, 105 if absent) and optional `resp` (a terminator string, or a byte count). It
writes `cmd` raw to the controller and returns the reply text (`{"value": ...}` with `ret_obj`).
READ. A client SHOULD NOT send controller command strings through `scope_send_cmd` that
it does not understand: they can change mount settings or move the mount (INFERRED).

R44. `MountConnection` (guider origin): `arrival` (boolean) and `device` (string) when the
serial link to the mount controller is lost or restored. READ. The imager also consumes it.

R45. [`mount_repower`][mr] drives GPIO lines in a fixed sequence (about 200 ms of sleeps) and
replies after it. INFERRED: this power-cycles the mount electronics, so the mount may disconnect
and lose its position. There is no parked or mode check. READ. A client SHOULD expect
`MountConnection` events afterwards (INFERRED).

R46. `MountUpdate` is an F event (`working` → terminal) from the imager's mount-firmware write
worker. No progress members beyond the F set. READ. The worker has no model check. It starts at
imager start-up when the device has the flashing tool installed, no done-marker exists for this
boot, and the persisted `write_mountboot` flag is set. It can also start from a start-up
command-line option. READ. On success it clears the flag and writes the marker, so it runs at
most once per flag setting. READ. A client cannot start it through the control API. Which models
ship the tool and set the flag: the guider sets the flag, on any model, when the mount controller
does not answer the guider's version query after five attempts on connect and no done-marker
exists for this boot; it clears the flag after a successful version check. READ (64-bit). The
firmware update package does not ship the flashing tool for any model; it only installs the mount
firmware image. Whether the tool is present therefore depends on the device's base system
image. READ (package, both builds); unresolved (base image).

R47. [`is_func_occupy_mount`][ifo] returns true while any of `Stack`, `EqModePA`, `3PPA`,
`AutoGoto`, `ScanSun`, `ObjectTrack`, `GoPixel` is active or planet correction is on. It is not
a hardware-busy probe. READ. Firmware 9.75: the list has 8 names, with `MotionMonitor` first;
`SmartFollow` is not in it. READ. Several handlers (`start_track_object`, `start_smart_follow`, `start_func`, `start_motion_monitor`,
`start_record_avi`, `start_scan_planet`) now call a relay check that probes the peer process
with this method (203 when occupied) and, for the recording variants, with `is_func_work` for
`AviRecord` and `MotionMonitor` (524); handlers such as `iscope_match_target_name` and `start_auto_focuse` use
the relay-only form with no probe. See [special-modes.md](../special-modes.md#object-tracking).
Whether `start_auto_goto` and `start_solve` use it is not confirmed. A client SHOULD check it before manual moves (INFERRED use).

## Meridian flip

R48. [`set_merid_setting`][sms] takes an object or `[object]` and patches `merid_over_min`
(integer, >= 0, else 204), `merid_before_min` (signed integer) and `merid_recalibrate` (boolean
or integer), and persists them. Missing keys keep their values; `{}` succeeds. Non-object params
give 107, a non-integer minute value 104 and a wrong-type `merid_recalibrate` 106.
Configuration-write failures are not reported. READ. Minute units are INFERRED from the names.

R49. [`get_merid_setting`][gms] returns only `merid_recalibrate`; the minute values cannot be
read back through it. READ. OBSERVED 2026-10-12: code 0 with a result holding only
`merid_recalibrate` (boolean).

R50. [`get_merid_delta`][gmd] reads no params and returns `target_merid_delta_min`,
`merid_over_min` (a negative stored value reads as 0), `merid_before_min` and
`is_below_horizon`. The delta is the hour delta `h` converted as `(h < 0 ? h + 12 : h) * 60`. The
call refreshes the coordinate cache when it is older than 5000 ms and fails with 207 when no
valid coordinates exist. READ. The hour delta is `h = RA - LST` (hours, wrapped to ±12), so a
positive value means the target has not yet crossed the meridian (east) and a negative value
means it has (west). READ. When `|h|` exceeds 6 h the device measures the delta to the lower
meridian instead. READ. The local sidereal time comes from the mount controller via the guider.
INFERRED.

R51. `MeridianFlip` (`state` `start`/`complete`/`fail`, `count`) and `MountSettle` (`start`/
`complete`) come only from the flip step of the legacy sequence capture and the legacy
autosave-plan capture. READ. The app has no handler for either. READ. The ViewPlan path never
performs a meridian flip and never emits these events. READ.

### Meridian delta result

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`get_merid_delta`](../../../docs/control/methods/get_merid_delta.md) returns
`{target_merid_delta_min, merid_over_min, merid_before_min, is_below_horizon}`. The `_min` members
are minutes (INFERRED). A negative hour delta is shifted by 12 h before conversion. 207 when no
target coordinates are cached. READ.

## Motion events

All are broadcast to every 4700 connection (guider-origin events via R6). F = common function
event (`state` in `idle`/`working`/`complete`/`fail`/`cancel`, `lapse_ms`, optional `stage`,
`route`; `error`/`code` on `fail`). See [events-overview.md](../events-overview.md).

| Event | Origin | Shape | Trigger |
|---|---|---|---|
| [ScopeGoto](../../../docs/control/events/ScopeGoto.md) | guider; imager (nested) | F + `close` (guider) or `cur_ra_dec`, `dist_deg` (imager) | `scope_goto`, auto-goto |
| [ScopeHome](../../../docs/guider/events/ScopeHome.md) | guider | F + `close`, `equ_mode` (`complete`) | `scope_park` |
| [ScopeMoveToHorizon](../../../docs/guider/events/ScopeMoveToHorizon.md) | guider | F + `close` | `scope_move_to_horizon` |
| [ScopeTrack](../../../docs/guider/events/ScopeTrack.md) | guider | `state` on/off, `tracking`, `manual`, `route`, `error`/`code` | tracking change |
| [MountMode](../../../docs/guider/events/MountMode.md) | guider | `equ_mode` | successful mode write (`scope_set_eq_mode`) |
| [MoveByAngle](../../../docs/guider/events/MoveByAngle.md) | guider | `state` start/moving/complete/fail, `value` | `scope_move_left_by_angle` |
| [MountConnection](../../../docs/guider/events/MountConnection.md) | guider | `arrival`, `device` | serial link change |
| [AutoCloseMount](../../../docs/guider/events/AutoCloseMount.md) | guider | none | repeated read failure |
| [MountUpdate](../../../docs/control/events/MountUpdate.md) | imager | F | mount firmware write |
| [AutoGoto](../../../docs/control/events/AutoGoto.md), [AutoGotoStep](../../../docs/control/events/AutoGotoStep.md) | imager | see R19 | `start_auto_goto` |
| [MeridianFlip](../../../docs/control/events/MeridianFlip.md), [MountSettle](../../../docs/control/events/MountSettle.md) | imager | legacy state strings | legacy sequence, legacy autosave plan |

R52. No ordering is guaranteed between a reply and the events of the operation it started, or
between events from different workers. READ. Clients MUST key on `Event`, `state` and `route`,
not on arrival order.

[gmd]: ../../../docs/control/methods/get_merid_delta.md
[gms]: ../../../docs/control/methods/get_merid_setting.md
[sms]: ../../../docs/control/methods/set_merid_setting.md
[mr]: ../../../docs/control/methods/mount_repower.md
[ifo]: ../../../docs/control/methods/is_func_occupy_mount.md
[sab]: ../../../docs/guider/methods/scope_abort_slew.md
[sts]: ../../../docs/guider/methods/scope_set_track_state.md
[sp]: ../../../docs/guider/methods/scope_park.md
[seq]: ../../../docs/guider/methods/scope_set_eq_mode.md
[srd]: ../../../docs/guider/methods/scope_get_ra_dec.md
[sgs]: ../../../docs/guider/methods/scope_get_state.md
[smh]: ../../../docs/guider/methods/scope_move_to_horizon.md
[smv]: ../../../docs/guider/methods/scope_move.md
[sgt]: ../../../docs/guider/methods/scope_get_track_state.md
[sge]: ../../../docs/guider/methods/scope_get_equ_coord.md
[sgh]: ../../../docs/guider/methods/scope_get_horiz_coord.md
[ssc]: ../../../docs/guider/methods/scope_send_cmd.md
