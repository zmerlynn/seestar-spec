# Mosaic capture

Scope: the tele-camera star-view mosaic, in which the device enlarges and rotates a virtual
canvas, walks the mount across a grid of centers inside it and stacks the frames onto that
canvas. It covers the `mosaic` parameters of
[`iscope_start_view`](../../docs/control/methods/iscope_start_view.md) and
[`set_view_plan`](../../docs/control/methods/set_view_plan.md) targets, the calculator member
`mosaic` of [`set_setting`](../../docs/control/methods/set_setting.md), the `mosaic` object of
[`get_setting`](../../docs/control/methods/get_setting.md), how the center list is generated
and traversed, and how a mosaic ends. Starting a view is in
[viewing-and-exposure.md](viewing-and-exposure.md); live stacking in [stacking.md](stacking.md);
plan timing in [plan-scheduling.md](plan-scheduling.md); mount moves in
[mount-and-motion.md](mount-and-motion.md). Per-method detail stays in the catalog cards.

App names: “Mosaic Mode” and the “Framing” screen send the `mosaic` object; its “Magnification” and
“Rotation Angle” controls match `scale` and `angle` (INFERRED). Not every framing label means mosaic
capture. Names are the English strings of iOS app 3.4.0; links are READ (app call sites) unless
marked.

## Conventions

As in [plan-scheduling.md](plan-scheduling.md#conventions): RFC 2119 words bind clients;
sentences about what "the device" does are descriptions. Labels are **READ** (firmware 9.31,
static analysis; firmware 9.75, app 3.4.0 deltas are tagged as such), **OBSERVED**, **INFERRED** and
**unresolved**. READ is the 64-bit imager build unless stated; [timing-and-errors.md: 32-bit build](mosaic/timing-and-errors.md#32-bit-build)
says what the 32-bit build shares. Nothing here was executed on a device.

Notation used in formulas:

- `T(x)`: conversion to a signed integer, truncating toward zero.
- `f32(x)`: the value rounded to single precision; arithmetic inside `f32(...)` is done in
  single precision.
- `W0`, `H0`: the camera width and height reported by the camera SDK, swapped when the camera
  reports a 90-degree rotation. They are not compiled-in constants. READ.
- `s`: the requested `scale`; `a`: the requested `angle`.

Firmware 9.75, app 3.4.0 replaced the center-list planner ([grid-and-movement.md: The firmware 9.75 planner](mosaic/grid-and-movement.md#the-firmware-975-planner)).
Statements about the spiral, the pitch and `F = num*N - 1` are firmware 9.31 behaviour and are
kept as written; each carries a 9.75 note where it changed. The parser, the enable predicate and
the canvas arithmetic are not known to have changed. 9.75 additionally lets a mosaic goto start
an ordinary stack ([R8c in stacking.md](stacking.md#sky-replay-and-star-trail-decay-firmware-975));
[`iscope_start_view`](../../docs/control/methods/iscope_start_view.md) gains the members
`goto_capt_type`, `goto_capture_settings` and `stack_exp_ms` and the codes 104 and 209
([viewing-and-exposure.md](viewing-and-exposure.md)); the mosaic files do not otherwise describe them.

Several stages call imported libraries (image rotation, star matching, coordinate and
refraction routines, the camera SDK). Their behaviour is outside the analysed binaries; where a
rule depends on it, the label says so.

## Overview

```
 iscope_start_view / plan target {mosaic:{scale, angle, star_map_angle}}
        |  parser: stores three floats, -999 when absent (Parameters and acceptance)
        v
 view setup: star_map_angle absent? -- yes --> parameters reset (1, 0, 361)
        | no
        v
 parameters applied: canvas = camera size x scale; enable predicate (Enable predicate)
        v
 first frames: orientation may be recalculated (grid-and-movement: Orientation)
        v
 center list: firmware 9.31: spiral of rotated grid points inside the canvas;
              firmware 9.75: rectangular strict-overlap grid (grid-and-movement: The firmware 9.75 planner);
              each position repeated 3/2/1 times (9.31) or 4/3/2 times (9.75) by exposure (grid-and-movement: Traversal)
        v
 per frame: star matching locates the current image; within 100 px of the
            current center -> next center; otherwise a correction move (grid-and-movement: Movement)
        v
 list exhausted -> a new round is generated (grid-and-movement: Traversal)
        v
 ends only by stop: plan timer, stop_func / iscope_stop_view, or a fatal error (timing-and-errors: Timing, Error propagation)
```

R1. A mosaic has no completion of its own. Rounds repeat until the view is stopped. READ /
INFERRED ([grid-and-movement.md: Traversal and per-center repetition](mosaic/grid-and-movement.md#traversal-and-per-center-repetition)). A client MUST bound a mosaic by a plan duration or an explicit stop.

## Parameters and acceptance

The `mosaic` object is parsed only after both `target_ra_dec` numbers parsed; a non-object is
ignored. READ. Parser behaviour (all READ):

| Member | Absent | Present |
|---|---|---|
| `star_map_angle` | stored as -999 (sentinel) | any number; non-number 102 |
| `scale` | stored as -999; `angle` is not read | any number; non-number 102 |
| `angle` | stored as -999 | read only when `scale` is present, then required (102 if missing or non-numeric) |

R2. The parser has no range check: zero, negative, very large and fractional values are
accepted. No grid-size, row, column or overlap member is read. READ. Acceptance (reply 0) says
nothing about whether the mosaic will be applied or succeed.

R3. The parameters are applied at view setup, not at parse time. If the stored
`star_map_angle` is the sentinel (within 0.1 of -999), the device resets the mosaic parameters
to scale 1, angle 0, star-map angle 361 instead of applying the request. Otherwise it applies
all three. READ. INFERRED: a target that sends `scale` and `angle` but omits `star_map_angle`
is parsed and echoed, yet runs with the reset values, which do not enable a mosaic
([Enable predicate](#enable-predicate)). A client that wants a mosaic MUST send all three members.

R4. Echoes of `mosaic` in `ViewPlan` / `Target` events, the held plan and `get_setting` show
stored values. They do not prove that a capture used them. READ (stored values) / INFERRED.

R5. When applied, the parameters are compared with the stored ones: a value within 0.1 of -999
is not stored, and a change smaller than 1e-6 is ignored. The canvas size is recomputed on
every application. The angle is truncated to an integer, not rounded; `star_map_angle` is kept
as a float. READ (firmware 9.31). Firmware 9.75, 64-bit build: direct view and plan targets share mosaic parsing, followed by later application during star-view setup. Application truncates the requested angle to a stored signed integer. If the setters report a change and setting notifications are not suppressed, building the notification synchronously computes an estimate using that stored integer. Frame initialization stores actual frame dimensions and builds the live list, passing the angle through integer-to-float-to-integer conversion. Later list regeneration uses half-away-from-zero rounding of the recovered angle. Unchanged parameters need not produce that notification; the parser therefore establishes no unconditional first planner call. Firmware 9.31, 64-bit build retains the parser/application distinction and uses the older planner. READ. Firmware 9.75, 32-bit initialization also round-trips its stored angle through float; full request-order parity across builds remains unresolved.

App practice (READ, app 3.3.2; not a device rule): the app's slider steps are consistent with a
scale of 1.0 to 2.0 in steps of 0.1 and an angle of -90 to 90 degrees (INFERRED from the
control construction), with half-up rounding of scale and nearest rounding of angle. The app's
own "has mosaic" test is `scale != 1 || angle != 0`, which differs from the device's
([Enable predicate](#enable-predicate)).

R6. A client SHOULD keep `scale` within 1.0 to 2.0 and `angle` within -90 to 90 unless it has
tested other values. The device does not enforce these. INFERRED.

## Enable predicate

R7. Applying the parameters selects mosaic mode exactly when

```
abs(scale) > 1.01  ||  abs(angle) > 0.1
```

evaluated on the input floats (before angle truncation), compared in double precision. READ.
`star_map_angle` does not take part. The predicate selects; it never rejects or clamps.

Consequences, INFERRED: scale 1.5 with angle 0 enables a mosaic; scale 0.5 with angle 0 does
not; scale 1 with angle -90 does; scale 1.005 with angle 0 does not. A negative scale with
magnitude above 1.01 enables it. When the predicate switches mosaic mode on, the device
installs the mosaic stacker as the live stacker. READ. Mosaic enabling is applied when the live
stacker is next selected, before the next stacked frame. A selected starry/wide stack type takes
precedence over the mosaic predicate. Any change of the mosaic state, the capture type, the
star-trails setting or the drizzle setting discards the current stack. READ. Star-trails sessions
do not use the wide-mosaic path. READ. The meaning of the individual capture types involved is
unresolved.

## Chapter map

| Part | Covers | Rules |
|---|---|---|
| [mosaic/grid-and-movement.md](mosaic/grid-and-movement.md) | Canvas and pitch arithmetic, candidate spiral and margins, grid size, the firmware 9.75 planner, per-center repetition, movement, orientation. | R8 to R21, R10a to R10f |
| [mosaic/timing-and-errors.md](mosaic/timing-and-errors.md) | Plan timer interaction, duration estimate, 32-bit build, error propagation, validation appendix. | R22 to R30 |

## Open questions

- Which way a positive sky-map rotation `u` turns the drawn mosaic frame on screen, and whether the
  map is drawn zenith-up with azimuth increasing to the right (the condition under which the device
  recovers `u` in alt-azimuth mode). The zero direction and the absence of a fixed cardinal meaning
  are settled in [R20a](mosaic/grid-and-movement.md#orientation).
- The imported rotation, star matching, coordinate and refraction routines' exact behaviour.
- Firmware 9.75: the exact results of the imported sine, cosine and star-matching routines, and bit-exact 32-bit parity of the planner arithmetic. The step derivation, route order and ordinary movement request are settled ([R10a to R10d](mosaic/grid-and-movement.md#the-firmware-975-planner), [R15 to R17](mosaic/grid-and-movement.md#movement)). The wire effect of the mosaic goto source (R8c in stacking.md) and of the stitch-error text is unresolved.
- Firmware 9.31: which runtime camera takes the wide pitch branch; which request selects the
  starry/wide stack type that enables the wide-mosaic branch, and how its 207 status reaches the
  client.
- Allocation failure for large or invalid canvases; mapping of container exceptions.
- Source units of the exposure settings behind R13 and R26.
- Physical sky span of an observed grid; hardware dimensions and pixel scale per model.
- Bit-exact 32-bit parity.
