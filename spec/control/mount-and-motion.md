# Mount and motion

This chapter covers mount control at the JSON method layer: goto, manual moves, sync,
tracking, park and home, arm open and close, equatorial mode, the meridian-flip settings, and
the events that report motion. It sits on the command channel described in
[session-handshake.md](session-handshake.md) and the event stream in
[events-overview.md](events-overview.md). Polar alignment and sensor calibration are in
[polar-alignment.md](polar-alignment.md); scheduled plans are in
[plan-scheduling.md](plan-scheduling.md). Mosaic moves are in [mosaic.md](mosaic.md) and the plan
pre-start window in [plan-scheduling.md: The worker](plan-scheduling.md#the-worker); both are out of scope here.
Per-method parameters and error tables live in the catalog cards linked below.

## Conventions

Keywords and labels are used as in [plan-scheduling.md: Conventions](plan-scheduling.md#conventions):
MUST/SHOULD/MAY bind clients; **READ** = seen in firmware 9.31 by static analysis,
**OBSERVED** = seen on a device (dated), **INFERRED**, **unresolved**. READ says what code does,
not that the motor then moves. No mount behaviour in this chapter was OBSERVED on a device; the
only OBSERVED fact is one meridian-setting reply (R49).

Basis: static analysis of firmware 9.31 (64-bit imager and guider builds; 32-bit builds where
stated) and Android app 3.3.2.

Two processes matter here:

- the **imager** (main process), serving JSON on TCP 4700, the port a client normally uses;
- the **guider** (mount process), serving JSON on TCP 4400. It owns the mount driver.

## Where a call is executed

R1. A request on 4700 is first looked up in the imager's method table. If no imager method of
that name exists (internal code 103 `method not found`), the imager forwards the **original
request text** to the guider on 4400 and sends back the guider's reply. READ. This is a
fallback for any unknown name, not a list of mount names.

R2. Forwarding is disabled for a client served from the guest table. The guest table is used
when guest mode is on, a guest table exists, and the client is neither the master nor a local
or internal client. Such a client gets code 103 for guider-only names. READ. A client that needs
mount control SHOULD hold the master role (see [session-handshake.md](session-handshake.md)).

R3. The imager waits up to 10000 ms for the guider's reply. READ. If the guider does not answer
in that time, or cannot be reached, the client receives error 103 (`method not found`) for the
forwarded request. READ. A guider reply is passed through verbatim without validation, so a
malformed guider reply reaches the client as-is. READ. A client therefore cannot tell an unknown
method from a forwarding failure by the code alone. INFERRED. A client SHOULD apply its own
timeout above 10 s for forwarded calls.

R4. Forwarding applies to single requests only. Inside a JSON-RPC batch, guider-only and unknown
method names are not forwarded; each such element gets error 103 in the batch reply. READ.
Clients MUST NOT batch mount calls.

R5. Before forwarding, the imager may (re)connect to the guider. On reconnect it sends
`speed_move_ratio` to the guider and refreshes mode and LED settings. READ. So even a forwarded
getter can have side effects. A stable connection avoids this path, but a client cannot
observe that. INFERRED.

R6. Guider events reach 4700 clients. The imager reads lines from 4400; a line containing the
exact substring `"Event":"` is re-broadcast unchanged on 4700. READ. The check is lexical
(spacing matters). The auxiliary wide-camera imager process does not forward guider events, so
duplicates do not arise from it. READ.

R7. A client MAY connect to 4400 directly. The guider accepts direct client connections on 4400.
Like 4700, it requires the client-verification handshake (see
[session-handshake.md](session-handshake.md)) before serving the client. READ. Local connections
such as the imager's relay are exempt. INFERRED (from the shared local-connection rule).

### Routing table

| Area | Executed by the imager (4700) | Executed by the guider (4400, forwarded from 4700) |
|---|---|---|
| Goto | [`start_auto_goto`][sag], [`start_auto_goto_pixel`][sagp], [`stop_auto_goto`][stag] | [`scope_goto`][sg], [`scope_abort_slew`][sab], [`can_goto`][cg], [`scope_is_moving`][sim] |
| Manual motion | [`start_func`][sf] (`GoPixel` centring), [`not_move`][nm], [`can_move`][cm] | [`scope_speed_move`][ssm], [`scope_fine_move`][sfm], [`scope_move_left_by_angle`][sml], [`speed_move_ratio`][smr] |
| Sync | [`scope_sync_planet`][ssp] | [`scope_sync`][ss] |
| Manual motion (cont.) | - | [`scope_move`][smv] |
| Tracking | - | [`scope_set_track_state`][sts], [`scope_get_track_state`][sgt] |
| Park / arm | - | [`scope_park`][sp], [`scope_move_to_horizon`][smh] |
| Mount mode | [`check_pa_alt`][cpa] (reads mode) | [`scope_set_eq_mode`][seq] |
| Position | [`get_merid_delta`][gmd] | [`scope_get_ra_dec`][srd], [`scope_get_state`][sgs], [`scope_get_equ_coord`][sge], [`scope_get_horiz_coord`][sgh] |
| Raw controller | - | [`scope_send_cmd`][ssc] |
| Meridian | [`get_merid_setting`][gms], [`set_merid_setting`][sms] | - |
| Power / busy | [`mount_repower`][mr], [`is_func_occupy_mount`][ifo] | - |

The guider has further `scope_*` getters and setters (slew rate, guide rate, location, time,
pier side, beep volume, connection parameters); see `docs/guider/methods/`. READ.

R8. The Android app also sends [`scope_move_to_horizon`][smh], [`scope_get_track_state`][sgt],
[`scope_move`][smv], [`scope_get_equ_coord`][sge], [`scope_get_horiz_coord`][sgh] and
[`scope_send_cmd`][ssc] on 4700. READ (app). None is in the imager tables and all six are
registered in the guider dispatch table, so they are forwarded by R1. READ. All six handlers
are analysed: `scope_move_to_horizon` (R38), `scope_get_track_state` (R35), `scope_move` (R38a),
and `scope_get_equ_coord`, `scope_get_horiz_coord` and `scope_send_cmd` (R43). READ.
`scope_get_equ_coord` has the same recovery side effects as `scope_get_ra_dec` (R42), and
`scope_get_track_state` may emit `ScopeTrack`. A client MUST NOT assume a name beginning
`scope_get_` is free of side effects.

## Common rules for guider calls

R9. Reply envelope as on 4700: success has `result` and `code` 0; failure has a flat `error`
string and nonzero `code`, no `result`. The outer layer adds `method`, `id`, `jsonrpc` and
`Timestamp`. READ. Code 0 means "accepted" (worker started or command acknowledged), never
"motion finished". READ.

R10. Parameter binding (guider). READ:

- Coordinate pairs bind from `{ra, dec}` or positional `[ra, dec]`. A bare scalar is not bound.
- One-value parameters bind from `{name: v}` or `[v]`. `[true]` and `[{"tracking": true}]` are
  both accepted where the handler selects a member from the first element; a bare scalar works
  only where the card says so (`scope_set_track_state`).
- `scope_speed_move`, `scope_fine_move` and `speed_move_ratio` take named objects only.
- Numbers accept JSON integers and reals. Reals are parsed as 32-bit floats before widening;
  expect about 7 significant digits.
- Boolean parameters accept a JSON boolean or an integer (nonzero = true), unless the card says
  the handler tests for a real boolean.
- Unknown object members are ignored.

R11. Codes common to mount handlers. READ:

| Code | Label | Typical meaning |
|---|---|---|
| 315 | `mount is not connected` | no mount object or not connected |
| 210 | `not supported` | driver lacks the capability (slew, home, track control, motion) |
| 203 | `equipment is moving` | current movement type does not admit this command |
| 108 / 106 / 104 | parameter type errors | float / bool / int expected |
| 536 | `view plan is already running` | see `scope_park` |

Further codes are forwarded from the driver. They are not enumerated. READ.

R12. RA is in **hours** and Dec in **degrees** for `scope_goto`, `scope_sync` and
`start_auto_goto`. READ. `scope_sync_planet` takes no coordinates; the RA it passes on to
`scope_sync` is divided by 15 first, so hours are INFERRED there. The device applies no epoch
conversion to `scope_goto`, `scope_sync` or `start_auto_goto` coordinates. READ. Where the device
itself starts from J2000 catalogue positions (plan targets), it precesses them to the current date
before commanding the mount. READ. Solve results are converted from J2000 to the current date
when a solve-parameter flag is set; `start_solve` sets it by default and the block-solve path
takes it from its caller (see [solving-and-annotation.md R5](solving-and-annotation.md#plate-solving)).
READ. The block-solve path converts to the current date for the polar-alignment exposure
solve, the auto-goto retry solve and the stacking re-centre solve. It keeps J2000 for the
three-point polar-alignment measurement solve and for the photometry solves (the photometry
check and photometry during stacking). READ (64-bit build; 32-bit not checked). Clients SHOULD
send coordinates of date (JNow). INFERRED.

## Chapter map

| File | Contents | Rules |
|---|---|---|
| this file | Conventions, where a call is executed, routing table, common rules for guider calls. | R1 to R12 |
| [mount-and-motion/goto-and-manual-motion.md](mount-and-motion/goto-and-manual-motion.md) | Raw and solved goto, joystick, fine and angle moves, the movement-permission flag, sync. | R13 to R32 |
| [mount-and-motion/tracking-park-and-state.md](mount-and-motion/tracking-park-and-state.md) | Tracking, park/home and the arm, equatorial mode, position and connection state, meridian flip, motion events. | R33 to R52 |

## Open questions

- Firmware 9.75: the effect of the compass-synced marker called by sync and of the changed
  move-round signatures (see the two chapters); the 32-bit build was not compared.
- Controller coordinate limits.
- `scope_move_to_horizon`: axle-to-sky relation in equatorial mode, stopping distance (needs a
  device test).
- `scope_speed_move` angle zero point and sense; physical unit of the native speed (needs a
  device test); the app's re-send interval.
- Controller behaviour when told to move a parked (folded) mount, and which motions the general
  stop halts (needs a device test).
- 32-bit build parity beyond the primary effects of `scope_goto`, `scope_speed_move`,
  `scope_park`, `scope_set_track_state`, `scope_get_ra_dec` and `scope_sync`, which were
  established separately.
- The order of the `ScopeGoto`/`ScopeTrack` events relative to the `scope_goto` reply
  ([goto-and-manual-motion R15](mount-and-motion/goto-and-manual-motion.md#raw-slew-scope_goto)).
  unresolved. Partial tracing suggests the reply is written only after the watcher worker's start
  call returns, but confirming this needs tracing into the watcher's thread-entry function for an
  actual synchronization point; a good candidate for a dedicated follow-up static-analysis pass.
- Which epoch (J2000 or of-date) the controller reports in `scope_get_state`
  ([tracking-park-and-state R43](mount-and-motion/tracking-park-and-state.md#position-and-connection-state)).
  unresolved; not determined by the device firmware.
- Whether the mount-flashing tool ships on a given device depends on the base system image, not
  the firmware update package
  ([tracking-park-and-state R46](mount-and-motion/tracking-park-and-state.md#position-and-connection-state)).
  unresolved (base image).

[sag]: ../../docs/control/methods/start_auto_goto.md
[sagp]: ../../docs/control/methods/start_auto_goto_pixel.md
[stag]: ../../docs/control/methods/stop_auto_goto.md
[sf]: ../../docs/control/methods/start_func.md
[nm]: ../../docs/control/methods/not_move.md
[cm]: ../../docs/control/methods/can_move.md
[ssp]: ../../docs/control/methods/scope_sync_planet.md
[cpa]: ../../docs/control/methods/check_pa_alt.md
[gmd]: ../../docs/control/methods/get_merid_delta.md
[gms]: ../../docs/control/methods/get_merid_setting.md
[sms]: ../../docs/control/methods/set_merid_setting.md
[mr]: ../../docs/control/methods/mount_repower.md
[ifo]: ../../docs/control/methods/is_func_occupy_mount.md
[sg]: ../../docs/guider/methods/scope_goto.md
[sab]: ../../docs/guider/methods/scope_abort_slew.md
[cg]: ../../docs/guider/methods/can_goto.md
[sim]: ../../docs/guider/methods/scope_is_moving.md
[ssm]: ../../docs/guider/methods/scope_speed_move.md
[sfm]: ../../docs/guider/methods/scope_fine_move.md
[sml]: ../../docs/guider/methods/scope_move_left_by_angle.md
[smr]: ../../docs/guider/methods/speed_move_ratio.md
[ss]: ../../docs/guider/methods/scope_sync.md
[sts]: ../../docs/guider/methods/scope_set_track_state.md
[sp]: ../../docs/guider/methods/scope_park.md
[seq]: ../../docs/guider/methods/scope_set_eq_mode.md
[srd]: ../../docs/guider/methods/scope_get_ra_dec.md
[sgs]: ../../docs/guider/methods/scope_get_state.md
[smh]: ../../docs/guider/methods/scope_move_to_horizon.md
[smv]: ../../docs/guider/methods/scope_move.md
[sgt]: ../../docs/guider/methods/scope_get_track_state.md
[sge]: ../../docs/guider/methods/scope_get_equ_coord.md
[sgh]: ../../docs/guider/methods/scope_get_horiz_coord.md
[ssc]: ../../docs/guider/methods/scope_send_cmd.md
