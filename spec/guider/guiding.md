# Guiding workflow and other guider commands

Part of the [guider chapter](index.md). This file covers the guiding workflow (preconditions,
states, methods and a typical sequence), the guider's mount, time and other commands, and the
imager's dither settings. Labels:
[index.md: Conventions](index.md#conventions); parsing and reply rules: [index.md: Requests and parameter parsing](index.md#requests-and-parameter-parsing) and [Replies](index.md#replies).

## Guiding workflow

The guider is PHD-style: loop exposures, pick a star, calibrate, guide, and settle after
dithers. The method-to-event links below are READ where a handler path to the notifier was
traced and INFERRED where only the event's name and trigger are known.

### Preconditions

R23. Before guiding, the guide camera and mount MUST be connected: `set_connected`
(`{"camera":true,"mount":true}`; only JSON booleans act) or `set_all_connected` (`true`).
`get_connected` reports what is connected. READ. Mount commands fail with 315 when the mount
is not connected. READ.

R24. `set_exposure` sets the guide exposure in milliseconds (integer); `set_gain`,
`set_camera_binning` and `set_search_region` configure the camera. READ (see cards).

### States

INFERRED from the handlers and event names; the guider's internal state names are reported by
[`AppState`](../../docs/guider/events/AppState.md) and their values are not enumerated here.

| State | Enter by | Events (on entry or while in it) | Leave by |
|---|---|---|---|
| stopped | start; `stop_capture` | [`LoopingExposuresStopped`](../../docs/guider/events/LoopingExposuresStopped.md), [`GuidingStopped`](../../docs/guider/events/GuidingStopped.md) | `loop`, `guide` |
| looping | `loop` (reply 0, or 303) | [`LoopingExposures`](../../docs/guider/events/LoopingExposures.md) per frame | `find_star`, `guide`, `stop_capture` |
| star selected | `find_star`, `set_lock_position` | [`StarSelected`](../../docs/guider/events/StarSelected.md), [`LockPositionSet`](../../docs/guider/events/LockPositionSet.md) (READ) | `guide`, `deselect_star` |
| calibrating | `guide` when not calibrated or `recalibrate` true | [`StartCalibration`](../../docs/guider/events/StartCalibration.md) (READ), [`Calibrating`](../../docs/guider/events/Calibrating.md), then [`CalibrationComplete`](../../docs/guider/events/CalibrationComplete.md) or [`CalibrationFailed`](../../docs/guider/events/CalibrationFailed.md) | calibration end |
| guiding | calibration complete; `guide` when calibrated | [`StartGuiding`](../../docs/guider/events/StartGuiding.md), [`GuideStep`](../../docs/guider/events/GuideStep.md) per frame | `stop_capture`, `set_paused` (star loss does not leave it) |
| settling | after `guide` start or `dither` | [`SettleBegin`](../../docs/guider/events/SettleBegin.md), [`Settling`](../../docs/guider/events/Settling.md), [`SettleDone`](../../docs/guider/events/SettleDone.md) | settle done or timeout |
| paused | `set_paused` true | [`Paused`](../../docs/guider/events/Paused.md) | `set_paused` false ([`Resumed`](../../docs/guider/events/Resumed.md)) |

Star loss while guiding yields [`StarLost`](../../docs/guider/events/StarLost.md) per affected frame and, past a threshold,
[`GuideStarLostTooMuch`](../../docs/guider/events/GuideStarLostTooMuch.md); [`LockPositionLost`](../../docs/guider/events/LockPositionLost.md) reports a lost lock target. READ (event triggers).

Star loss does not stop guiding. While guiding, each lost frame yields `StarLost` and guiding
continues. After about ten losses in the recent window the guider also emits
`GuideStarLostTooMuch`, still without stopping. READ. While calibrating, `StarLost` is emitted
and calibration continues. READ. With only a star selected, a lost star returns the guider to
the unselected state: `LockPositionLost` is emitted, then `StarLost`. READ. `LockPositionLost`
is also emitted when the lock position is invalidated for other reasons. READ. A client that
wants guiding to stop on star loss MUST stop it itself. INFERRED.

### Methods

R25. `loop` starts continuous guide-camera capture; params are not read. Reply 0 means
looping was scheduled, not that a frame arrived; 303 means it could not start. READ. See
[`loop`](../../docs/guider/methods/loop.md).

R26. `find_star` auto-selects a guide star from the current image; params are not read. On
success `result` is the star position `[x, y]` (pixels) and the guider sets the lock position
there (a `LockPositionSet` follows). Errors: 316 no star found, 300 internal. READ.
`find_star` works on the most recent stored guide frame and does not expose a new one. It
fails with 316 if there is none, and it is refused while calibrating. READ. A client SHOULD
call it only while looping. INFERRED. See
[`find_star`](../../docs/guider/methods/find_star.md).

R27. `set_lock_position` takes `{x, y, exact}` or `[x, y, exact]`: `x` and `y` are required
pixel numbers (108), `exact` is optional boolean, default false (106 if wrongly typed). It
fails with 304 while calibrating or guiding. READ. `get_lock_position` returns `[x, y]`, or
`null` when no valid lock position is stored. READ. `deselect_star` clears the selected star
and guider state. READ.

R28. `guide` starts calibration (if needed) and guiding. READ. Params:

```text
{"recalibrate": <bool|int, optional>, "settle": {"pixels": <number>, "time": <number>, "timeout": <number>}}
  or  [<recalibrate>, <settle object>]
```

`settle` is required and all three members are required (102 for a missing member). READ.
`settle.pixels` is, despite its name, a distance in arcseconds. The guider converts it to
pixels using the guide camera's arcseconds per pixel, and uses it as pixels if the scale is
unknown. READ (conversion) / INFERRED (unit). `time` and `timeout` are whole seconds. READ
(floor) / INFERRED (unit). The imager fills `pixels` from `settle_arcsec` ([Imager dither settings](#imager-dither-settings)). READ. A
stored device setting can suppress a requested recalibration. READ. Errors: 107 (bad shape or
settle), 106 (bad recalibrate), 268 (a dark-library build is in progress). READ. Reply 0 means
guiding was accepted, not that it settled. READ. See
[`guide`](../../docs/guider/methods/guide.md).

R29. `dither` takes `{amount, settle}` or `[amount, settle]`; `amount` is a required number
(108) and `settle` uses the same rules as `guide`. `amount` is a dither amplitude in
guide-camera pixels, multiplied by a stored scale factor; its sign is ignored. The RA offset is
a random fraction (−1 to 1) of it, or follows a spiral in spiral mode. READ (arithmetic) /
INFERRED (pixel unit). Dither is refused unless guiding. READ. Reply 0 means the dither
was accepted, not that settling ended. READ. A client SHOULD wait for `SettleDone` before
resuming exposures and MUST check its `Status` (0 = success). INFERRED. See
[`dither`](../../docs/guider/methods/dither.md).

R30. `set_paused` takes `{paused, type}` or `[paused, type]`. `paused` is required (106);
`false` resumes and ignores `type` entirely. With `paused` true, a missing `type` or any string
other than `full` selects the ordinary pause, `full` selects full pause, and a non-string
`type` gives 105. READ. An ordinary pause keeps the guide camera exposing and frames flowing,
but no corrections are issued. A full pause also stops scheduling guide-camera exposures until
resumed. READ.
`get_paused` returns a boolean. READ.

R31. `stop_capture` stops acquisition (looping and guiding); params are not read and the
reply is always 0. Reply 0 does not mean the worker has finished. READ.

R32. Calibration management: `clear_calibration` (params absent = both; or an array of
`mount`, `ao`, `both`, case-insensitive; 109 for others), `flip_calibration` (flips RA
calibration; 207 on failure), `get_calibrated` (boolean), `set_auto_load_calibration` /
`get_auto_load_calibration`, `set_dec_guide_mode` / `get_dec_guide_mode`. READ. See cards.

R33. `guide_pulse` sends one manual pulse: `{direction, amount, which}` or positional.
`amount` is an integer duration in milliseconds (104), `direction` a string (105):
`north`/`south`/`east`/`west` or `up`/`down`/`left`/`right`, case-insensitive; `which` selects
mount (default) or AO. It fails with 318 when not connected, 319 while calibrating or guiding,
320 if the move fails. READ. Pulses can move the telescope; a client MUST NOT send them during
an exposure it cares about. INFERRED.

R34. Algorithm tuning: `get_algo_param_names`, `get_algo_param` and `set_algo_param` address a
guide algorithm by `axis` (`ra`/`x` or `dec`/`y`) and `name`. READ. The names depend on the
axis's algorithm. Hysteresis has `hysteresis`, `aggression` and `minMove`. Lowpass has
`slopeWeight` and `minMove`. Lowpass2 has `aggressiveness` and `minMove`. Resist-switch has
`aggression`, `fastSwitch` and `minMove`. READ. `get_algo_param` returns a number;
`set_algo_param` takes a numeric `value` and the value persists per axis. READ. Errors for
`set_algo_param`: 105 (missing member), 108 (`value` not a number), and 322 when no guide
algorithm is available, the `name` is unknown for that axis's algorithm, or the value is out of
range. 323 belongs to `get_algo_param` only. READ. `minMove` is in pixels. INFERRED.

R34a. An out-of-range `value` is not simply discarded: the guider replaces it with the
substitute below, applies and persists that, and still answers 322. READ (64-bit; 32-bit not
checked). A client SHOULD read the value back with `get_algo_param` after a 322.

| Algorithm | `name` | Accepted range | Substitute on 322 |
|---|---|---|---|
| Hysteresis | `hysteresis` | 0 to 1 | clamped to 0 or 1 |
| Hysteresis | `aggression` | above 0, up to 2 | 0.1 if ≤ 0; 2.0 if above 2 |
| Hysteresis | `minMove` | ≥ 0 | 0.1 |
| Lowpass | `slopeWeight` | ≥ 0 | 5.0 |
| Lowpass | `minMove` | ≥ 0 | 0.2 |
| Lowpass2 | `aggressiveness` | ≥ 0, no upper limit | live value unchanged; 80.0 is persisted |
| Lowpass2 | `minMove` | ≥ 0 | 0.2 |
| Resist-switch | `aggression` | above 0, up to 1 | 1.0 |
| Resist-switch | `minMove` | above 0 | 0.1 |
| Resist-switch | `fastSwitch` | any number; non-zero means on | never rejected |

Resist-switch `aggression` is a fraction from 0 to 1, read and written without scaling, not a
percentage. READ.

### Typical sequence

```text
client                                         guider
  |-- set_all_connected [true] ------------------>|
  |<-- result 0 ---------------------------------|
  |-- loop -------------------------------------->|
  |<-- result 0 ---------------------------------|
  |<== LoopingExposures {Frame:1}, {Frame:2} ... |
  |-- find_star --------------------------------->|
  |<== LockPositionSet {X,Y}                     |   (order vs reply not guaranteed)
  |<-- result [x, y] ----------------------------|
  |-- guide {settle:{pixels,time,timeout}} ------>|
  |<-- result 0 ---------------------------------|
  |<== StartCalibration, Calibrating ...,        |
  |    CalibrationComplete                       |
  |<== StartGuiding, SettleBegin, Settling ...,  |
  |    SettleDone {Status:0}, GuideStep ...      |
  |-- dither {amount, settle} ------------------->|
  |<-- result 0 ---------------------------------|
  |<== GuidingDithered, Settling ..., SettleDone |
  |-- stop_capture ------------------------------>|
  |<-- result 0 ; GuidingStopped,                |
  |    LoopingExposuresStopped                   |
```

The order of events in this diagram is INFERRED from their triggers; only the individual
method-to-notifier paths named in R26 to R30 are READ.

## Mount, time and other commands

The guider also owns the mount link. Its `scope_*` methods (goto, sync, park, speed move,
tracking, location, time, guide rate) and `pi_set_time` write mount serial commands. READ.
`scope_goto` (`{ra, dec}` or `[ra, dec]`, RA hours and Dec degrees) and `scope_park` report
progress through the [`ScopeGoto`](../../docs/control/events/ScopeGoto.md) and [`ScopeHome`](../../docs/guider/events/ScopeHome.md) function events; tracking changes emit
[`ScopeTrack`](../../docs/guider/events/ScopeTrack.md). READ. Details are on the cards, for example
[`scope_goto`](../../docs/guider/methods/scope_goto.md),
[`scope_park`](../../docs/guider/methods/scope_park.md),
[`scope_speed_move`](../../docs/guider/methods/scope_speed_move.md).

The full serial command set is in [mount-serial-commands.md](mount-serial-commands.md).

Firmware 9.75: after the mount link connects, the guider sends the command `:GP#` (command type 3,
reply ignored), and the start-up motor-current check no longer skips when the charge temperature
is 10 degrees C or lower. READ (64-bit). The remaining guider mount handlers are identical to
firmware 9.31. Real guider changes in 9.75 are in authentication, the FITS and image header,
Wi-Fi and access point, and mount, history and temperature code; these were only diffed coarsely
and are unresolved.

R35. `shutdown` stops the guider's event server (not the host). The reply is built before the
server stops but may not be delivered. READ. A client SHOULD NOT send it; the imager depends on
the guider.

R36. `speed_move_ratio` is normally sent by the imager on (re)connect (R7). A client that sends
it changes the guider's manual-move scaling. READ.

## Imager dither settings

The imager on TCP 4700 keeps a shared set of dither and settle settings and mirrors one of them,
`ra_only`, into the guider. These are control-service methods, executed by the imager, not
guider methods. Basis: static analysis of firmware 9.31 (64-bit imager build; the 32-bit
handlers are registered, helper parity probable). No app emitter was found for either method in
app 3.3.2 (READ, bounded search). When the imager dithers, it sends the guider `dither` (R29)
with its stored `amount`, and a `settle` built from `settle_arcsec` (sent as `pixels`), `time`
and `timeout`. It allows 10 s for the reply, then waits for `SettleDone`. READ. `interval` only
schedules dithers on the imager and is not sent. READ (not sent) / INFERRED (frame count).

R37. [`get_dither`](../../docs/control/methods/get_dither.md) (MUTATOR / established, tier B)
reads no params. It first asks the guider for its `dither_raonly` setting (`get_setting`,
waiting up to 10000 ms) and overwrites the cached `ra_only` only when the guider's reply
contains the expected compact `"dither_raonly":true` or `false` literal; otherwise it keeps the
cached value and still succeeds. It then returns all nine members: `enable`, `ra_only`,
`timeout_stop`, `wait_guide_settle` (booleans), `amount`, `settle_timeout_sec`,
`settle_time_sec`, `interval` (integers) and `settle_arcsec` (number). READ. The units of
`amount` and `interval` are not established (INFERRED: guider amplitude and frame count). A
client SHOULD allow for a reply delay of up to about 10 s.

R38. [`set_dither`](../../docs/control/methods/set_dither.md) (MUTATOR / probable, tier C)
takes an object, or an array whose first element is that object (107 otherwise). Every member
is optional and patches the current value. An unknown member or a wrong type gives 109 (106 for
`wait_guide_settle`, which also accepts an integer), and nothing is written until all members
have parsed. READ. Valid ranges, with the fallback written when a value is outside them:

| Member | Valid | Fallback |
|---|---|---|
| `amount` | 1..30 | 1 |
| `settle_timeout_sec` | > 0 | 99999 |
| `settle_arcsec` | > 0 and <= 16 | 2 |
| `settle_time_sec` | 1..30 | 5 |
| `interval` | 0..30 | 1 |

The handler applies and persists all values, fallbacks included, and only then returns 204 if
any value was out of range. A client MUST NOT read 204 as "nothing changed"; it SHOULD re-read
with `get_dither` after a 204. READ. It then sends the guider `set_setting` with
`dither_raonly`, waiting up to 10000 ms; a guider failure is logged and does not fail the call,
and there is no rollback. READ.
