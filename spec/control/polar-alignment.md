# Polar alignment and mount sensors

This chapter covers polar alignment and the mount's orientation sensors at the JSON method
layer. That includes three-point polar alignment (3PPA), equatorial-mode alignment (EqModePA),
compass calibration, g-sensor calibration and the balance sensor. All of these methods run in
the imager on TCP 4700. They move the mount through the guider, as described in
[mount-and-motion.md](mount-and-motion.md). Events reach the client as described in
[events-overview.md](events-overview.md). Per-method detail is in the linked catalog cards.

App names: “Polar Align” is equatorial-mode alignment. “Level sensor calibration” (on the “Level &
Compass Calibration” page, with “Adjust Level”) is the G-sensor calibration and balance display.
“Compass Calibration” with “Manual Calibration” is the compass calibration; its “Auto Calibration”
is the automatic one (INFERRED). “Horizontal calibration” and “3 Point Calibration” match the
three-point calibration (INFERRED). Names are the English strings of iOS app 3.4.0; links are READ
(app call sites) unless marked.

## Conventions

Keywords and labels are used as in [plan-scheduling.md: Conventions](plan-scheduling.md#conventions).
**READ** means seen in firmware 9.31 by static analysis. **OBSERVED** means seen on a device,
with a date. The other labels are **INFERRED** and **unresolved**. No behaviour in this chapter
was OBSERVED on a device.

Basis: static analysis of firmware 9.31 (imager, 64-bit) and Android app 3.3.2, with deltas from firmware 9.75 / app 3.4.0 where tagged.

F events use the common function-event shape: `state` is one of `idle`, `working`, `complete`,
`fail` or `cancel`. F events also carry `lapse_ms`, an optional `stage` and `route`.
`error` and `code` are present only on `fail`, and `cancel` omits `code`. READ.

## Modes

A single entry point, [`start_polar_align`][spa], starts one of three procedures. READ:

| Mount mode | `is_one_star` | Procedure (type) | F event | Status event | Summary |
|---|---|---|---|---|---|
| alt-azimuth | ignored | three-point (`altaz_3p`) | `3PPA` | `3PPA` | Exposes and plate-solves at several mount positions, then computes the polar-axis error. |
| equatorial | false | equatorial three-point (`eq_3p`) | `EqModePA` | `3PPA` | The three-point stages, then gyro tracking of the error. |
| equatorial | true | one-star gyro (`eq_1p`) | `EqModePA` | `3PPA` | One exposure and solve, then gyro tracking of the error. |

R1. The imager selects the procedure from the mount's equatorial mode. READ. In alt-azimuth mode
it always runs the three-point procedure and ignores `is_one_star`. In equatorial mode
`is_one_star` true selects the one-star gyro procedure and false selects the equatorial
three-point procedure. READ. F events are named `EqModePA` for both equatorial procedures and
`3PPA` for alt-azimuth; the per-stage status event is named `3PPA` in every mode. READ. If the
mount mode cannot be read the start fails with 254. READ. If the three-point setting `is_pa_3p`
(R2) is false, the start returns success without starting any worker. READ. That this is the
legacy image-pair mode (R13) is INFERRED. A client SHOULD read the mount mode first and follow
the matching F event.

## Settings

R2. [`get_3p_pa_setting`][g3s] returns `is_pa_3p` (boolean) and `rotate_angle`.
[`set_3p_pa_setting`][s3s] patches them and persists the changed fields. If `params` is not an
object (an array included), the call fails with 107. `is_pa_3p` takes a boolean or an integer;
`rotate_angle` takes a number, truncated toward zero. No range is checked. Its unit is degrees (INFERRED). READ.

## Run control

R3. [`start_polar_align`][spa] takes an optional object. READ:

- `is_one_star` (boolean, or integer with nonzero = true; default false);
- `restart` (boolean, or integer with nonzero = true; default false);
- `dec_pos_index` (integer, default 3; an integer outside 1..5 gives 204).

A member of the wrong type keeps its default, and unknown members are ignored. Absent, null,
scalar and array `params` run with all defaults: an array is not a positional form. READ.

Checks, in order. READ:

1. a ViewPlan is running: 536, checked before the parameters are parsed;
2. `dec_pos_index` is an integer outside 1..5: 204;
3. the mount mode cannot be read: 254 `mount operation failed`;
4. an alignment worker is already running, or the active status cannot be resumed: 268
   `operation is in progress`.

A session stays active from start until `stop_polar_align`. READ. With `restart` true, when the
worker is running, or when a session is active and the mount is in equatorial mode, the handler
first stops the alignment worker and the gyro thread and, if a session is active, restores the
saved settings and clears the session; that stop can block. READ. Then:

- the worker is still running: 268;
- the requested type differs from the active session's type: the old session is restored and
  cleared, and the start is fresh;
- no active session: fresh start;
- an active equatorial three-point (`eq_3p`) session: the worker resumes with its kept stage;
- an active alt-azimuth or one-star session: 268.

READ. So `restart` true gives a fresh start in equatorial mode. A paused alt-azimuth session
gives 268, with or without `restart`, until `stop_polar_align`. READ. Starting the procedure
stops any autogoto, view or exposure first. The handler records the caller's connection as the
recipient of alignment results. It does not check whether the mount is parked. READ. The app's start command sends `{"is_one_star": true}` when its star setting is
1 and omits `params` otherwise; its reset command always sends `{"restart": <bool>}`, adding
`dec_pos_index` when a position is chosen. READ (app). A client SHOULD open the arm first (see
[mount-and-motion/tracking-park-and-state.md: Park, home and the arm](mount-and-motion/tracking-park-and-state.md#park-home-and-the-arm)). INFERRED.

R4. [`pause_polar_align`][ppa] stops the alignment worker and the gyro thread. It may block
while they exit. It does not restore settings, and the session stays active. READ. Only an
equatorial three-point session can be resumed, by `start_polar_align` without `restart` (R3).
When the alt-azimuth worker ends the session is cleared; when an equatorial worker ends the
session remains active until `stop_polar_align` or a restart. READ.

R5. [`stop_polar_align`][stpa] stops the threads and, if a session was active, restores the
settings saved at start and clears the session. READ.

R6. [`clear_polar_align`][cla] overwrites the stored results with sentinel values. The image
files are kept. READ.

| State | Request | Result | Next state |
|---|---|---|---|
| idle (no session) | `start_polar_align` | 0, worker started | running |
| running | `start_polar_align` | 268 | running |
| running | `start_polar_align` `restart` | 0, old run stopped and restored, fresh worker | running |
| paused, `eq_3p` | `start_polar_align` | 0, worker resumes at its kept stage | running |
| paused or ended, equatorial | `start_polar_align` `restart` | 0, fresh worker | running |
| paused or ended, `eq_1p` | `start_polar_align` | 268 | unchanged |
| paused, `altaz_3p` | `start_polar_align` (any `restart`) | 268 | unchanged |
| session of another type | `start_polar_align` | 0, old session cleared, fresh worker | running |
| any | ViewPlan active + `start_polar_align` | 536 | unchanged |
| running | `pause_polar_align` | 0, after the threads stop | paused (session active, settings not restored) |
| running, paused or ended | `stop_polar_align` | 0 | idle (settings restored) |
| running, `altaz_3p` | worker ends | F `complete`/`fail` | idle (session cleared) |
| running, equatorial | worker ends | F `complete`/`fail` | ended (session still active) |
| any | `clear_polar_align` | 0 | results reset |

The state names are descriptive; they are not wire values. INFERRED.

## Three-point progress (3PPA)

[3PPA](../../docs/control/events/3PPA.md) has two emitters. READ. The F branch is sent only in
alt-azimuth mode; in equatorial mode the F events are named `EqModePA` (R1). The status branch is
named `3PPA` in every mode. READ.

**F branch.** The common F members are present, plus `percent` and `calib_fail_autogoto`.
`offset` and `equ_offset` (two numbers each) are present only when they are not the -999
sentinel (`abs(v+999) > 0.1`). On `fail` the code is 207 by default, 252 when the automatic
goto fails, or a code copied from the failing step. READ. Code 252 is `auto goto failed`.
READ.

**Status branch.** This branch has the same structure that [`get_3p_pa_state`][g3p] returns.
READ:

| Member | Type | Presence | Meaning |
|---|---|---|---|
| `state`, `state_code` | string, int | always | stage (table below); not an error code |
| `auto_move`, `auto_update` | bool | always | settings of the run |
| `paused` | bool | always | true when the alignment worker thread is not running |
| `detail` | object | run active | per-stage progress (table below); may be empty |
| `lapse_ms` | unsigned int | run active | milliseconds since the status started |
| `retry_cnt` | int | run active | retry count |
| `pa_error` | object | valid result | `total`, `x`, `y` in degrees and `total_arcsec`, `x_arcsec`, `y_arcsec` (each × 3600) |

`pa_error` is present only when both `x` and `y` are outside the band ±0.1 around the -999
sentinel. READ.

| `state_code` | Kind | `detail` members |
|---|---|---|
| 0 | idle | none |
| 2, 7, 12, 15 | exposure | `lapse_ms`, `total_ms` (the exposure time) |
| 3, 8, 13, 16 | plate solve | `lapse_ms`; `star_number` when it is 0 or more |
| 6, 11 | wait | `lapse_ms`, `total_ms` 4000 |
| others up to 17 | start, calculation and movement stages; names are in the event card | none (empty object) |

The stage is kept after a pause or stop, so a stopped run still reports its last stage. The
stage enumeration has no complete, fail or cancel value; those come only from the F branch.
READ.

R7. A client SHOULD drive its progress display from `state_code` and `detail`. It SHOULD take
the final error from `pa_error` or from [`get_polar_axis`][gpa]. READ (shape); INFERRED (use).

R8. [`GSensorMove`](../../docs/control/events/GSensorMove.md) (no members) reports that the g-sensor detected mount motion, and the 3PPA
calibration is then cleared. READ. A client SHOULD warn the user and expect to restart the
alignment. INFERRED.

## Equatorial-mode alignment (EqModePA)

R9. [EqModePA](../../docs/control/events/EqModePA.md) is an F event. On `complete` with valid
offsets it also carries `total`, `x` and `y`. READ.

R10. `complete` is sent before gyro work that is still in progress, and it may repeat. A later
`cancel` can follow a `complete`. READ. A client MUST NOT treat the first `complete` as the end
of the run. It SHOULD treat the run as ended only after `stop_polar_align` or a `cancel`/`fail`
event. INFERRED.

R11. One-star (`eq_1p`): the device sends `working`, then after a single exposure and solve
sends `complete` with the polar error. It then keeps re-sending `complete` with the updated error
as the gyro detects movement (about once a second at most) until stopped, when it sends
`cancel`. READ. Failures before tracking end with `fail` and a code; a failure to start the gyro
can follow the first `complete`. READ. Equatorial three-point (`eq_3p`): stages report through
`3PPA` status events; on success the device sends `complete` and then re-sends `complete` with
the updated error while gyro tracking runs. READ. Stopping that gyro tracking sends no further
terminal event. INFERRED. A client MUST treat repeated `complete` events as live updates, not as
a new run.

## Results and image slots

R12. [`get_polar_axis`][gpa] reads no params. It returns `dist_arcsec`, `dist_x_arcsec`,
`dist_y_arcsec` (degree errors × 3600) and `success`. In three-point mode the distances come
from the three-point error. In legacy mode they come from the saved image pair, and a successful
calculation also returns `centre_deg` and `polar_deg`, each `[azimuth, altitude]` in degrees.
If the current calculation fails but an earlier distance is cached, the reply has `success`
false, the cached distances and no arrays. It fails with 207 when the legacy centre cannot be
computed or no cached distance exists. READ. A successful call rewrites the cached distances
and can refresh the stored location, so it is not side-effect free (tier B). READ.

R13. The legacy image-pair path uses two slots, 0 and 1. READ:

- [`set_polar_align_image`][spi] takes the slot as an integer or `[int]`; any other form is
  ignored. An integer outside 0..1 gives 204. With no valid slot the device picks the slot
  itself, alternating between calls. It copies the latest temporary solve (WCS) file into the slot and gives
  207 when the image matches the other slot (MD5), when the copy fails or when the solve time
  cannot be read. If the MD5 cannot be computed, the duplicate check is skipped. The copy may
  already have happened when an error is returned; the slot's solve time and the next implicit
  slot are updated only on success.
- [`rm_polar_align_image`][rpi] reads no params and deletes both slot files, ignoring errors. It
  does not reset the stored solve times or the next implicit slot.
- [`get_polar_align_image`][gpi] reads no params and returns `[bool, bool]`, whether each slot
  file exists. It has no error branch.

## Location checks

R14. [`check_pa_alt`][cpa] reads no params and returns `result.is_valid`. It is true when the
mount is not in equatorial mode or the mode cannot be read. In equatorial mode it is true when
`abs((90 - balance_angle) - abs(latitude)) < 5` degrees. An unsuitable orientation is
`is_valid` false, not an error. READ. In equatorial mode a location failure gives a reply that
has `error`, a `result` (`is_valid` true) and two `code` members: the failure code, then 0. A
location outside longitude (-360.1, 360.1) or latitude (-90.1, 90.1) gives 204; other failures
with no assigned code give 207. READ. A client MUST treat any reply that has an `error` member
as a failure, even if `result` is present (see [errors.md](errors.md)).

R15. [`cali_user_location`][cul] takes an optional pair, `{ra, dec}` or `[ra, dec]`, with RA in
hours and Dec in degrees. A missing or invalid pair is not an error. READ. When the pair parses,
the test setting is 1 and the user location loads, the device replaces its in-memory
location-offset pair; otherwise it reports the previous pair. Nothing is written to
configuration and nothing moves. READ. The result always has `calib_location` (integer) and may
have the two-number arrays `effect_offset_deg`, `offset_deg` and `offset_deg_3ppa`, each only
when its value is valid. `effect_offset_deg` can appear twice in one reply. READ. A client
SHOULD use a JSON parser that tolerates duplicate keys. `offset_deg` is the device tilt
measured by the balance sensor, in degrees, resolved into two horizon-frame components relative
to the azimuth of the given target at the current time and location. READ. No precession is
applied, so the coordinates are treated as of date. INFERRED. The method is a test facility: it
fails with 210 unless the corresponding test setting is enabled. READ. `offset_deg_3ppa` reports
the location offset found by the three-point procedure and is valid only under a different test
setting. READ.

## Compass calibration

The user turns the mount through a full circle while the device samples the magnetometer.
INFERRED (procedure). The state values are READ:

| Value | State |
|---|---|
| 0 | idle |
| 1 | sampling |
| 2 | cancelling |
| 3 | calculating |

| From | Request / trigger | Result | To |
|---|---|---|---|
| 0 | [`start_compass_calibration`][scc] | 0; sampling timer starts (1 ms first delay, 100 ms interval) | 1 |
| ≠0, or calculation thread running | `start_compass_calibration` | 207 | unchanged |
| 1 | [`start_scope_move_round`][smr] | 0; move worker starts | 1 |
| ≠1 | `start_scope_move_round` | 207 | unchanged |
| 1 | [`stop_compass_calibration`][stc] `{force: ≠0}` | 0; move worker and timer stopped (cancel) | 2, then 0 |
| 1 | `stop_compass_calibration` `{force: 0}` | 0; move worker and timer stopped, samples frozen, calculation thread starts | 3 |
| 3 | `stop_compass_calibration` `{force: 0}` | 0 | 3 |
| other | `stop_compass_calibration` | 207 | unchanged |
| 3 | calculation ends | `CompassCalibration` complete/fail | 0 (INFERRED) |

`force` is read only as a JSON integer in an object; a boolean or any other form counts as 0.
The stop can block while the move worker exits. READ.

R16. [`get_compass_state`][gcs] returns `result.number`, the number of samples. Despite its name
it does not return the state value. READ.

R17. [`start_scope_move_round`][smr] starts a worker that moves the mount for the sampling and
replies at once. The trajectory and rate are not established; a turn through a full circle is
INFERRED from the name. When the round worker ends it sends
[ScopeMoveRound](../../docs/control/events/ScopeMoveRound.md) `{"result": "success" | "fail"}`.
READ. That the thread started by this call runs that worker is INFERRED from the names.

R18. [CompassCalibration](../../docs/control/events/CompassCalibration.md) has two producers.
READ:

- The magnetometer sampling callback sends `working` with `sector_id`, `covered`, `total`,
  `samples` and `route`, as sectors are covered. There is no independent timer.
- The state-with-route helper sends `complete` or `fail` with `route` (possibly empty). `error`
  and `code` are added only for a code greater than 0. The calculation thread passes 0. The
  move step sends `fail` with code 241, 300 or 320.

The heading circle is divided into 12 sectors of 30° numbered 0-11 from heading 0, and `total`
is 12. READ. A `working` event is sent once each time a new sector is first covered, so a run
sends at most 12; there is no other throttle. READ. The device stops sampling and calculates on
its own when all 12 sectors are covered and no new sector has been seen for 2 s (after at least
20 samples), or 65 s after start. READ. Terminal `fail` from the calculation carries no code. No
codes other than those above were found. READ. A client MUST accept
`working`, `complete` and `fail`, and MUST NOT require `code` on `fail`.

```text
client                       imager:4700                  guider (mount)
  |-- start_compass_calibration -->|                             |
  |<-- 0 --------------------------|  state 1, sample every 100 ms
  |-- start_scope_move_round ----->|---- move commands -------->|
  |<-- 0 --------------------------|                             |
  |<== CompassCalibration working (sector progress) ==============|
  |<== ScopeMoveRound {result} ====|  (order vs working events not established)
  |-- stop_compass_calibration {force:0} -->|  state 3, calculate
  |<-- 0 --------------------------|                             |
  |<== CompassCalibration complete | fail                        |
```

### Automatic compass calibration (firmware 9.75)

Firmware 9.75, app 3.4.0 adds [`start_compass_auto_calibration`][sca], which runs the sampling and
the mount rotation without the client driving `start_compass_calibration`,
`start_scope_move_round` and `stop_compass_calibration`. READ (64-bit; the 32-bit imager has the
same handler and the same code 560 site, other 32-bit details are not verified).

R18a. `start_compass_auto_calibration` takes no params and replies `result` 0 once the work has
started. READ. Errors: 524 if a calibration or the rotation thread already runs, 203 if the
mount is moving, and 560 if the mount's motion state cannot be read. If the rotation thread
cannot be started the reply carries a stale error code instead of a defined one. READ. It sets
the automatic flags, starts the same sampling worker as the manual flow ([Compass calibration](#compass-calibration)) and a
rotation thread that picks east or west from the right-ascension angle. The device reads two
mount registers to choose a safe direction. READ. A client MUST NOT also call
`start_scope_move_round` for the same run. INFERRED.

R18b. Stop reasons logged by the device are `all_sectors_idle`, `round_complete` and `timeout`.
After a coverage failure the device can resume sampling. READ. On success the device writes the
compass calibration to the stored sensor calibration (the same store that
[`get_sensor_calibration`][gsc] reads), writes a debug CSV in its temporary area, and sends the
guider `clear_az_state`. READ.

R18c. `CompassCalibration` `fail` carries `code` and `error` in firmware 9.75; in firmware 9.31
the calculation `fail` carried none (R18). `complete` is unchanged. READ. Codes
(texts are in [errors](errors.md#code-table)):

| Code | Cause (firmware 9.75) | Label |
|---:|---|---|
| 560 | Mount communication failed: the motion state or RA angle could not be read | READ |
| 561 | Rotation failed: the rotation-direction selection found no safe direction, or the automatic rotation failed with no code stored | READ |
| 562 | Rotation timed out (65 s) | READ |
| 563 | Sampling gate failed or sector coverage insufficient | READ (sampling and coverage branch; never returned by the fit-failure classifier) |
| 564 | Magnetic interference or field instability detected | READ |
| 565 | Calibration failed, generic | READ (the fallback inside the fit-failure classifier) |

The fit-failure classifier picks 564 when the interference flag is set or field instability was
detected, and otherwise the stored failure code, or 565 when none is stored; it never returns 563.
563 comes from the sampling and coverage branch (the sampling-gate failure, or sector coverage
still too low). 561 is also set by the sampling timer when the automatic rotation failed and no
code is stored yet. 562 is stored on timeout (more than 65 s after the start) only if no code is
stored yet. 565 also covers fewer than 10 samples after de-duplication and a failure to write the
result to the configuration store. The first code stored wins. READ (64-bit firmware 9.75).
`start_compass_auto_calibration` itself gives 524 if it already runs, 203 if
the mount is moving and 560 if the motion-state read fails. The routine reads the registers
`:GFR5#` and `:GFC1#`.

R18d. Fit and coverage thresholds (firmware 9.75, 64-bit). READ. The expected field magnitude
is 50.0 and a sample's residual is the absolute difference of its magnitude from 50.0 after the
fit. The fit fails if the residual standard deviation exceeds 10.0 or the largest residual exceeds
25.0, if the absolute determinant of the fit matrix is below about 1e-6, if an eigenvalue is below
about 1e-12, or if the condition number (square root of the largest over the smallest eigenvalue)
exceeds 10. The circle is divided into 12 sectors of 30 degrees and at least 6 must be covered.
If coverage fails while the calibration state is 3, the automatic rotation is not running and 65 s
have not elapsed, sampling resumes with no `fail` event; otherwise the `fail` event carries the
stored code, else 563. Interference is flagged when three consecutive field readings each differ
by more than 300.0 from the baseline, or when, over the last 50 samples, the median absolute
deviation from the midrange exceeds 8.0 (the units of 300.0 and 8.0 are INFERRED to be the raw
magnetometer unit). The sampling period is 100 ms. A successful result is written to the stored
sensor calibration (`msensor` valid flag and the x, y, x11, x12, y11, y12 values). Whether
the 9.31 build used the same thresholds was not diffed (unresolved); the 32-bit build has the
same failure strings and its parity is INFERRED.

A
client MUST NOT require a particular code and MUST accept any `code` on `fail`. Whether the
9.31 move-step codes (241, 300, 320) can still occur in 9.75 was not re-checked. READ (selection);
READ (561: no safe direction).

## G-sensor and stored calibration

R19. [`start_gsensor_calibration`][sgc] reads no params and fails with 268 if the calibration
thread is running. Otherwise it starts the named worker `CalibGSensor`, which replaces and
persists the balance-sensor calibration, and replies at once. The worker's lifecycle is reported
by the F event [CalibGSensor](../../docs/control/events/CalibGSensor.md); no members beyond the
F set are established. READ. [`stop_gsensor_calibration`][sgs] stops that worker by name and may
wait for it to exit; it ignores the stop result and always succeeds, even when nothing ran.
READ. Stopping a running g-sensor calibration ends it with `cancel`. READ. The calibration takes
10 samples about 0.5 s apart (about 5 s); it fails with 204 if the measured tilt is 20° or more.
READ. In the app, the procedure is: place the Seestar on a level surface, start the calibration
from the device calibration settings after a confirmation that it overwrites the existing values,
and do not touch the Seestar while it runs. The app refuses to start during an observation and
does not offer the control over a remote connection. On a 204 failure it tells the user to level
the tripod and retry, and to contact support if the tripod is already level. The app never sends
`stop_gsensor_calibration` from this screen. READ (app 3.3.2). The app does not check that the
surface is level. INFERRED.

R20. [`get_sensor_calibration`][gsc] returns:

- `balanceSensor` {`x`, `y`, `z`, `exist`};
- `compassSensor` {`x`, `y`, `z`, `x11`, `x12`, `y11`, `y12`, `exist`}.

READ.

R21. [`set_sensor_calibration`][ssc] fails with 107 if `params` is not an object. READ. A
`balanceSensor` member replaces the stored values as a whole: `x` defaults to -999 (the "not
calibrated" sentinel), and `y` and `z` default to 0. A sentinel component makes the stored
balance calibration invalid (`exist` false). A `compassSensor` member sets the compass `exist`
flag to true, even when the object is empty, and then patches only the members sent as JSON
reals: an integer token such as `5` is ignored, so send `5.0`. Neither object reads `exist`.
Sentinel and configuration-write failures are swallowed, so the reply is 0 and a partial write
can remain. READ. A client that writes `balanceSensor` MUST send all three axes, and a client
that writes `compassSensor` SHOULD send every member as a real and read the values back with
`get_sensor_calibration`.

## Balance sensor

R22. [BalanceSensor](../../docs/control/events/BalanceSensor.md) carries `code` and
`data` {`x`, `y`, `z`, `angle`}. `angle` is in degrees. READ. It is driven by a 100 ms timer,
but that rate is not guaranteed. READ. A client MUST NOT rely on the event rate.

R23. The device streams BalanceSensor from a background thread of the imager; no method starts
or stops it. READ. That the thread runs for the life of the imager is INFERRED. `code` is 0 for a
valid reading and 1 when the sensor could not be read, in which case the values are zero. READ.

## Open questions

- The full `state_code` name table and the stage-to-mount-position map for `dec_pos_index`.
- The label for code 320.
- Firmware 9.75: the stale code when the rotation thread cannot start (R18a).
- The units and frames of `offset` and `equ_offset`. The sign convention of `pa_error` x/y.

[spa]: ../../docs/control/methods/start_polar_align.md
[ppa]: ../../docs/control/methods/pause_polar_align.md
[stpa]: ../../docs/control/methods/stop_polar_align.md
[cla]: ../../docs/control/methods/clear_polar_align.md
[g3s]: ../../docs/control/methods/get_3p_pa_setting.md
[s3s]: ../../docs/control/methods/set_3p_pa_setting.md
[g3p]: ../../docs/control/methods/get_3p_pa_state.md
[gpa]: ../../docs/control/methods/get_polar_axis.md
[spi]: ../../docs/control/methods/set_polar_align_image.md
[rpi]: ../../docs/control/methods/rm_polar_align_image.md
[gpi]: ../../docs/control/methods/get_polar_align_image.md
[cpa]: ../../docs/control/methods/check_pa_alt.md
[cul]: ../../docs/control/methods/cali_user_location.md
[scc]: ../../docs/control/methods/start_compass_calibration.md
[sca]: ../../docs/control/methods/start_compass_auto_calibration.md
[stc]: ../../docs/control/methods/stop_compass_calibration.md
[smr]: ../../docs/control/methods/start_scope_move_round.md
[gcs]: ../../docs/control/methods/get_compass_state.md
[sgc]: ../../docs/control/methods/start_gsensor_calibration.md
[sgs]: ../../docs/control/methods/stop_gsensor_calibration.md
[gsc]: ../../docs/control/methods/get_sensor_calibration.md
[ssc]: ../../docs/control/methods/set_sensor_calibration.md
