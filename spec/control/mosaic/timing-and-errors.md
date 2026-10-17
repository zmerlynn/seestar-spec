# Mosaic timing, estimate and errors

Part of the [mosaic chapter](../mosaic.md). This file covers how a mosaic interacts with the
plan target timer, the duration estimate, what the 32-bit build shares, how errors propagate,
and a non-normative validation appendix. Labels and notation: [mosaic.md: Conventions](../mosaic.md#conventions).

## Timing and deadline interaction

R22. A mosaic plan target runs under the ordinary tele target timer
([plan-scheduling.md](../plan-scheduling.md#the-worker)); there is no mosaic exemption. READ.
The timer is armed before the view starts, so setup and the initial goto consume the same
budget. With entry sample `T0`, arm time `B` and stored end `E`, nominal expiry is
`B + 1000*floor((E-T0)/1000)` ms, not necessarily `E`. READ / INFERRED. The remaining-time
arithmetic is unsigned 64-bit, divided by 1000 and narrowed to a 32-bit integer of seconds.
READ.

R23. On expiry the timer callback requests a view stop. It does not itself set 513 `target time
out`; that code comes from the plan worker's own expired-end check. READ. Cancellation is
cooperative: the capture and move loop and the goto wait check the run flag; list generation
and imported library calls do not. READ.

R24. INFERRED consequences: a mosaic does not first finish all centers or rounds; it does not
stop exactly at the stored end; stop and cleanup latency, or a failed timer creation (logged
only), delay the next target, which starts late or fails with 513. No upper bound on stop
latency is established. The fine-move request wait, goto watchdog and duration estimate are
not mosaic timers.

R25. A client MUST size the target's `duration_min` for the coverage it wants and MUST NOT
expect the device to extend it for a mosaic. A direct `iscope_start_view` mosaic has no timer;
the client MUST stop it ([`iscope_stop_view`](../../../docs/control/methods/iscope_stop_view.md) or
[`stop_func`](../../../docs/control/methods/stop_func.md)). INFERRED from [R1](../mosaic.md#overview) and R22.

The final code reported for a stopped target is chosen among the guard, child and timeout
errors by the plan worker; a timer stop does not guarantee 513. READ / INFERRED.

## Duration estimate

R26. The device estimates a duration from one list, READ (firmware 9.31 definition of `F` in the
formula; the 9.75 definition follows):

```
t   = f32((double(X) / 1000.0) / 3600.0)        # X: signed exposure setting
out = f32( f32( f32(F) * t ) * 1.5 )            # F: list length, num*N - 1
```

`F` is converted from its low 32 bits; there is no integer rounding of the result. `X` is the
`exp_ms.stack_l` setting, which the device also multiplies by 1000 to get the stack exposure
in microseconds. READ (64-bit; identical in the 32-bit build, where `F` is already a 32-bit
integer). INFERRED: `X` is therefore in milliseconds
and `out` is hours, including a fixed factor of 1.5. `X` is a different setting from the
`E` of [R13](grid-and-movement.md#traversal-and-per-center-repetition).

R26a. Firmware 9.75, app 3.4.0 (READ): the formula (the factor `t` and the factor 1.5) is
unchanged. `F` is the size of the list returned by the 9.75 planner
([R10a to R10d](grid-and-movement.md#the-firmware-975-planner)), that is `num*N` with the
visit counts of [R13a](grid-and-movement.md#traversal-and-per-center-repetition), and `N` comes
from the rectangular grid. For the same inputs a 9.75 device therefore reports a larger
`estimated_hours` than a 9.31 device. A client MUST NOT compare estimates across firmware versions.

R27. `estimated_hours` is an estimate of one round, not a timeout, center limit or completion
promise. INFERRED. A client MUST NOT use it as a plan duration without its own margin.

R28. [`set_setting`](../../../docs/control/methods/set_setting.md) `{"mosaic":{"scale":s,
"angle":a}}` is a calculator. It builds a temporary planner from the current camera size,
returns `{estimated_hours}` at once and skips later members; it does not call the runtime
parameter setter, does not install capture settings and does not start or time anything.
`star_map_angle` is not read on this call; without `scale` nothing is calculated; a closed
camera gives 318. READ. The same absence of clamps applies ([R11](grid-and-movement.md#candidates-and-margins)).

R29. [`get_setting`](../../../docs/control/methods/get_setting.md) `mosaic` reports the stored
`scale`, `angle`, `star_map_angle`, the stored ratio as `star_map_ratio`, and
`estimated_hours` computed on the live planner. READ (members). `scale` is a unitless multiple
of the camera frame and `star_map_ratio` is a copy of `scale` taken when the live canvas was
last initialized (default 1). `angle` is stored and reported truncated to an integer and goes
unconverted to a rotation routine that takes degrees. `star_map_angle` is in degrees, with 361
meaning "no value" (the initial value). READ (64-bit; identical in the 32-bit build). That `angle` is in degrees and
`estimated_hours` in hours is INFERRED (R26).

The app computes its own estimate locally with a different routine and different rounding; it
is not the device's formula. READ (app).

## 32-bit build

Firmware 9.31: the 32-bit build shares the parser, the enable predicate, canvas arithmetic, the
width-dependent pitch, the strict 100-pixel margins, the spiral, the exposure repetition, the
estimate formula, the plan timer and the stop-on-expiry callback. READ. Firmware 9.75: the
32-bit build contains the new planner (R10f) and the visit counts and `F` definition of R13a
and R26a are assumed to match; this was not traced (INFERRED). Qualifications:

- Rotation coefficients are applied with separate multiply and add (64-bit: fused
  multiply-add). Strict-boundary decisions and truncated coordinates can therefore differ
  between builds; bit-exact parity is not established. READ / INFERRED.
- The pitch doubling compares the current camera identifier with the literal 1, not with a
  wide-camera variable. READ. Runtime identifiers are unresolved; see
  [grid-and-movement.md R9](grid-and-movement.md#pitch).
- Container growth is inlined with 32-bit capacity limits; the 64-bit length-error branch is
  not present in the same form. READ.
- Time is a 32-bit millisecond count compared unsigned; the target timer is armed before
  coordinate setup (64-bit: after). Long-uptime parity does not follow. READ / INFERRED.
- The 64-bit wide/dual routing and wide-mosaic branch are not established on this build.

## Error propagation

| Situation | Effect | Label |
|---|---|---|
| Parser: mistyped member, or `scale` without numeric `angle` | 102 `invalid params` on the request | READ |
| Mount reports tracking stopped at a limit | stack loop ends with 270 `below horizon` or 527 `alt exceed limit` | READ |
| Initial target below the horizon | 270 from the initial goto | READ |
| Initial goto refused | a specific mount error is kept; the generic 207 becomes 501 `mount goto failed`; transport failure gives 241 | READ |
| Initial solve fails | 251 `solve failed`, forwarded to the plan target | READ |
| Fine move refused or timed out | logged, capture continues ([R17](grid-and-movement.md#movement)) | READ |
| Later optional re-solve fails | capture continues | READ |
| Frame alignment problems (263, 264, 266, 530) | per-frame counters and retries, not automatically terminal | READ |
| First wide-mosaic absolute goto fails | stacking worker ends with status 207; how it reaches the client is unresolved ([grid-and-movement.md: Movement](grid-and-movement.md#movement)) | READ / unresolved |
| Wide-mosaic goto or wait fails | branch records 501 and exits its loop; final top-level code unresolved ([grid-and-movement.md: Movement](grid-and-movement.md#movement)) | READ / unresolved |
| Allocation or container failure | outside practical use; no error is defined and 249 is not implied ([grid-and-movement.md R11](grid-and-movement.md#candidates-and-margins)) | not applicable |
| Firmware 9.75: planner returns an empty list (canvas 200 pixels or less, or failed overlap or coverage check, [R10b, R10d](grid-and-movement.md#the-firmware-975-planner)) | no centers; no error code is tied to it in the code read | READ / INFERRED |
| Plan timer expiry | stop request; 513 only via the outer check (R23) | READ |

Only the stack loop's explicit error is propagated to the view and then to the plan target. A
logged failure or an error inside a child operation is not by itself the plan error. READ. No
dedicated scale-limit or center-count error exists. READ.

R30. A client SHOULD read the target's final `code` and the `Stack` and `AutoGoto` events to
learn why a mosaic ended, and MUST NOT infer a scale problem from a generic failure. INFERRED.

[`check_ai_process`](../../../docs/control/methods/check_ai_process.md) tests a saved image for
black gaps. The app calls it from a routine named for mosaic completion, but it says nothing
about whether the device finished its centers, and it neither stops the item timer nor ends a
round. READ (handler) / INFERRED.

## Appendix: Validation (non-normative)

The model and the worked values below describe firmware 9.31 (firmware 9.75 uses the
planner of [R10a to R10d](grid-and-movement.md#the-firmware-975-planner); the values are not
valid for it and have not been regenerated). A client can predict a firmware 9.31 grid offline with
this model of R8 to R13 (rotation per [grid-and-movement.md: Candidates and margins](grid-and-movement.md#candidates-and-margins),
INFERRED):

```
def centers(W0, H0, s, a, wide=False):
    W = int(f32(f32(W0) * s)); H = int(f32(f32(H0) * s)); A = int(a)
    q = int(((W * 220.0) / 1080.0) * 2.0) if wide else int((W / 1080.0) * 220.0)
    cx, cy = int(W / 2), int(H / 2)          # truncation toward zero
    out = [(cx, cy)]
    for each spiral candidate (cx + i*q, cy + j*q) in leg order 1,1,2,2,...:
        x', y' = rotate(candidate, about=(W*0.5, H*0.5), degrees=A)
        if 100 < x' < W-100 and 100 < y' < H-100: out.append((int(x'), int(y')))
    stop after a four-leg group with no acceptance
    return out
```

Worked values (INFERRED arithmetic; the camera size is illustrative, not a known model):

| `W0`x`H0` | scale | canvas | `q` | grid (cols x rows) | span, px |
|---|---|---|---|---|---|
| 2160x3840 | 0.5 (needs a nonzero angle to enable) | 1080x1920 | 220 | 3x7 | 440x1320 |
| 2160x3840 | 1.0 | 2160x3840 | 440 | 5x9 | 1760x3520 |
| 2160x3840 | 1.5 | 3240x5760 | 660 | 5x9 | 2640x5280 |

Pitch check: `W=1083` gives `q=220` on the ordinary branch and `441` on the wide branch (not
440), because truncation happens once at the end.

Predicate check ([R7](../mosaic.md#enable-predicate)): `(1.5, 0)` on, `(0.5, 0)` off, `(1, -90)` on, `(1.005, 0.05)` off.

Repetition and estimate check (firmware 9.31): with `E` of 5000000 and 45 positions, `F = 3*45 - 1 = 134`
nodes; with `X` of 10000, `out` is about `134 * (10/3600) * 1.5 = 0.558` hours.

On a device (only with permission and a safe sky position): start a star view with a mosaic of
scale 1.5 and angle 0 and all three members; confirm `Stack` progress and small fine moves;
then repeat without `star_map_angle` and confirm no mosaic movement ([R3](../mosaic.md#parameters-and-acceptance)). Compare a plan target
with a short `duration_min` against the stop time (R22).

Firmware 9.75 check (INFERRED arithmetic): with `E` of 5000000, a grid of `N` positions has `F = 4*N`
and, with `X` of 10000, `out` is about `4*N * (10/3600) * 1.5` hours; for `N = 45` that is about 0.75 hours.
