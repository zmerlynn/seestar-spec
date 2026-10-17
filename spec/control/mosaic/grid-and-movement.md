# Mosaic grid and movement

Part of the [mosaic chapter](../mosaic.md). This file covers the canvas and pitch arithmetic,
candidate generation, grid size, per-center repetition, movement between centers and the
orientation calculation. Labels, notation and parameters:
[mosaic.md](../mosaic.md): [Conventions](../mosaic.md#conventions), [Overview](../mosaic.md#overview), [Parameters and acceptance](../mosaic.md#parameters-and-acceptance) and [Enable predicate](../mosaic.md#enable-predicate).

Firmware 9.75, app 3.4.0 replaced the center-list planner. R9 to R12 and [Grid size](#grid-size) describe the
firmware 9.31 planner and stay as written; [The firmware 9.75 planner](#the-firmware-975-planner) describes the
9.75 planner and R13 gives both repetition rules.

## Canvas and grid generation

### Canvas

R8. The canvas is the camera frame scaled in single precision and truncated:

```
W = T(f32(f32(W0) * s))
H = T(f32(f32(H0) * s))
A = T(a)                       # integer planner angle
```

READ. There is no clamp before the canvas buffers are allocated, so canvas memory grows about
as `s^2`. READ (no clamp) / INFERRED (growth). Negative, huge or non-finite results go straight
to the imported allocator; this specification defines no outcome for them.

### Pitch

R9. Firmware 9.31: the pitch `q` between neighbouring candidates, in canvas pixels:

```
ordinary camera:  q = T((double(W) / 1080.0) * 220.0)
wide-camera id:   q = T(((double(W) * 220.0) / 1080.0) * 2.0)
```

Each is evaluated in double precision with a single truncation at the end. The branch is a
comparison of the current camera identifier with the wide camera's identifier; scale plays no
part in it. READ. Which runtime camera takes which branch is unresolved. On a live device,
`get_device_state` reported `camera` with 260 mm focal length and 2.9 µm pixels and
`second_camera` with 6 mm and 1.6 µm, so `second_camera` is the wide camera (2026-10-16;
OBSERVED values, INFERRED role). `get_camera_info` with the integers 0 and 1 returned only
all-zero default records, so the runtime identifiers were not tied to either camera. OBSERVED. On an
idle device with a camera open, `get_camera_info` without params returned code 0 and the telescope
camera record (chip `[2160,3840]` as reported, 2.9 µm, GR, colour, bins 1 and 2), matching the keyed `camera`;
integers 0 and 1 still returned the same default records afterwards (2026-10-16). OBSERVED. The
refresh therefore does not fill the per-ordinal cache, and the ordinal mapping stays unresolved. The planner is called
with the constants 220 (pitch base) and 3 (repetition base) at every call site used for
capture, estimation and regeneration. READ (firmware 9.31). Firmware 9.75 (READ): the pitch
argument is no longer used by the planner and the wide-camera branch is gone from it ([R10a](#the-firmware-975-planner)).

### Candidates and margins

R10. Firmware 9.31 generation, READ:

1. The integer center `(T(W/2), T(H/2))` (integer division toward zero) is appended
   unconditionally, without rotation or margin test.
2. Candidates walk an integer square spiral from that center: directions `(1,0)`, `(0,1)`,
   `(-1,0)`, `(0,-1)` in turn, legs of 1, 1, 2, 2, 3, 3, 4, 4, ... steps, each step `q` pixels.
3. Each candidate is rotated by `A` (converted to double) about the float point
   `(f32(W)*0.5, f32(H)*0.5)` with scale 1.0, by the imported rotation-matrix routine.
4. It is accepted only if the rotated double coordinates satisfy all four strict
   inequalities `100 < x' < W-100` and `100 < y' < H-100`. Accepted points are then truncated
   to integers and appended in spiral order.
5. The walk stops after a complete group of four legs in which no candidate was accepted.

The 100-pixel margin is fixed; it is not scaled. It is a different quantity from the
100-pixel arrival threshold of [Movement](#movement). READ.

R11. There is no mosaic-specific limit on the number of centers and no scale clamp. READ. The
list grows dynamically; only generic container and allocator limits apply, far beyond any
practical grid, so this specification defines no plan or RPC error for their failure. A client
MUST NOT expect an error such as "too many centers"; none exists.

Under the conventional meaning of the imported routine (INFERRED), the rotation is

```
x' = cx + cos(A)*(x-cx) + sin(A)*(y-cy)
y' = cy - sin(A)*(x-cx) + cos(A)*(y-cy)
```

with `A` in degrees: positive `A` is counterclockwise in an image with x to the right and y
down. That the argument is passed without a radians conversion is READ; the degree unit and
sign are the imported routine's semantics (INFERRED). Image directions are not celestial
directions ([Orientation](#orientation)).

### Grid size

Firmware 9.31. The result is a clipped, rotated lattice, not `rows = k*scale`. INFERRED from R9 and R10: for
an angle that is a multiple of 90, even canvas dimensions and `L > 200`, the count along an
axis of canvas length `L` is

```
n(L) = 2 * ceil((L/2 - 100) / q) - 1
center span = (n(L) - 1) * q          # pixels
```

that is, the integers `k` with `100 < L/2 + k*q < L-100`. Odd dimensions differ by half a
pixel between the integer start and the float rotation center; floating-point boundary cases
can differ. For other angles, count rotated candidates directly ([timing-and-errors.md: Appendix: Validation](timing-and-errors.md#appendix-validation-non-normative)).

R12. Firmware 9.31: because both `W` and `q` scale with `s`, the canvas extent and the pitch grow about
linearly with scale, while the counts tend to stay constant (they depend on aspect ratio and
the pitch branch), with steps from truncation and the fixed margin. A larger scale does not
request quadratically more centers. INFERRED. A client MUST NOT assume a fixed grid for a
given scale on all devices.

With image scale `P` arcseconds per pixel, the angular pitch is about `q*P/60` arcminutes and
the center span about `(n-1)*q*P/60`. The canvas covers about `W*P/60` by `H*P/60`; each
frame's footprint can extend past it and is cropped. These three extents differ. INFERRED.
Exact sky coverage also depends on pose, projection and tracking, which are outside this
protocol specification.

### The firmware 9.75 planner

R10a. Firmware 9.75, app 3.4.0 (READ): parameter initialization, the duration estimate (R26) and list regeneration (R14) all call a new planner, which builds an axis-aligned rectangular grid of centers on the canvas. The 9.31 planner's code is still present in the imager, but none of those three paths calls it; that nothing else calls it is INFERRED. The pitch argument of R9 and the wide-camera branch of R9 do not take part in the new planner.

The planner's footprint is the current frame width `Fw` and height `Fh` when both are positive. Otherwise each is the matching canvas dimension divided by the stored canvas scale (or by 1 when that scale is not positive), rounded half away from zero, with a minimum of 1. READ.

R10b. Firmware 9.75 (READ): the maximum step `Lmax` (canvas pixels) comes from an overlap bound evaluated at 1801 orientations. All arithmetic is binary64 and is evaluated in the order written. `k` is the binary64 value `0x1.9999999999998p-2`, which is 1 minus the next binary64 value above 0.6 (INFERRED from the 32-bit build, which computes it that way).

```
M = largest finite double
for i = 0 .. 1800:
    if i = 0: c = 1, t = 0
    else:     theta = ((i * 0.1) * pi) / 180;  c = |cos theta|;  t = |sin theta|
    for (a, b) in ((c/Fw, t/Fh), (t/Fw, c/Fh)):
        s = a + b
        v = ((a * 4) * b) * k
        D = fma(s, s, -v)                       (one rounding)
        q = sqrt(D) if D > 0 else 0
        L = (2*k) / (s + q) if s + q > 2^-52 else 0
        M = min(M, L)
Lmax = max(0, ceil(M) - 1)
```

`Lmax` is an integer-valued double: an integral `M` is still reduced by one. A canvas whose `W` or `H` is 200 or less, or an `Lmax` below 1, yields an empty list. INFERRED: `L` is the smaller root of `a*b*L^2 - (a+b)*L + k = 0`, i.e. the largest shift at which two aligned footprints still overlap by more than 0.6 at that orientation. The 0.1-degree scan is a finite sample, not a continuous optimum. The 32-bit build forms `D` with separate roundings (R10f).

The grid then has

```
ncols = max(1, ceil((W - 200) / Lmax - 1e-9) + 1)
nrows = max(1, ceil((H - 200) / Lmax - 1e-9) + 1)
```

columns and rows. READ. The 200 is consistent with the 100-pixel margin of R10 on each side (INFERRED). `Lmax` bounds the pitch but is not necessarily the pitch: each axis's pitch is fitted between margins that depend on the footprint and the requested rotation, and is floored. Each coordinate is placed symmetrically about the canvas center and then rounded half away from zero on its own, so the rounded grid need not be exactly symmetric; the middle coordinate of an odd count is the rounded canvas center. READ. Further margin checks, not specified here, can reject the candidate grid. The counts therefore do not guarantee that a grid is returned.

R10c. Firmware 9.75 (READ): the first position is an anchor at the canvas center, `(round(W/2), round(H/2))` rounded half away from zero. It need not be a grid position. The remaining order is defined on grid indices (column `x`, row `y`):

1. List the perimeters clockwise from the outside in. For bounds `left, right, top, bottom`: the top row left to right; the right column from `top+1` to `bottom`; if the bottom row is distinct, that row from `right-1` down to `left`; if the left column is distinct from the right one, that column from `bottom-1` down to `top+1`. Shrink each bound by one and repeat.
2. Reverse the whole list. Call it `Q`.
3. Find the first entry of `Q` with the smallest squared index distance `d` to `((ncols-1)/2, (nrows-1)/2)`. Ties keep the earlier entry. Let `j` be its zero-based index.
4. Reverse the prefix `Q[0 : j+1]` if `d > 1e-12`, otherwise the prefix `Q[0 : j]`. The rest of `Q` is unchanged.
5. After the anchor, append the pixel position of each entry of `Q` in order. Skip any entry whose integer coordinates equal the anchor.

For example (INFERRED from these rules), a 3 by 3 grid gives the anchor `(1,1)` and then `(0,1),(0,2),(1,2),(2,2),(2,1),(2,0),(1,0),(0,0)`. A 5 by 3 grid gives `(2,1)` and then `(3,1),(1,1),(0,1),...`, so successive positions are not always neighbours. The number of unique positions `N` is `ncols*nrows` plus one when no grid position coincides with the anchor; R13a's `F = num*N` counts the anchor. INFERRED.

R10d. Firmware 9.75 (READ): the planner checks the route at the requested rotation (not over the 1801 orientations of R10b) before returning it. The step from the anchor to the first grid position must overlap by strictly more than 0.6. A later position must overlap its predecessor by more than 0.6, or else an earlier position within a search window that is not specified here; once such an earlier reference has been used, later positions are also checked that way. The planner also rasterizes the rotated footprints into a mask at one-sixteenth scale, `max(1, ceil(W/16))` by `max(1, ceil(H/16))`, and requires zero uncovered mask pixels. A raster check does not prove exact continuous coverage (INFERRED). If any check fails, the planner returns an empty list. There is no retry with a larger grid. What a client sees for an empty list (no centers, so no mosaic movement) is INFERRED; no error code is tied to it in the code read.

R10e. Firmware 9.75 (READ): the planner is called when the parameters are initialized, when the duration estimate is computed (R26) and when frames are stacked and the list is regenerated. A 9.75 estimate is not always larger than the 9.31 estimate for the same inputs: a canvas with a dimension of 200 or less gives 9.75 an empty list and a zero estimate, while 9.31 always keeps its center. INFERRED (static counterexample).

R10f. Firmware 9.75, 32-bit build: the same planner exists. Parity of the arithmetic is not
established. READ (existence) / unresolved.

## Traversal and per-center repetition

R13. Firmware 9.31: each position is visited several times in a row, chosen from the raw stack-exposure
setting `E` when the list is generated. READ:

| `E` | visits per position `num` |
|---|---|
| `E <= 10000000` | 3 |
| `10000000 < E <= 20000000` | 2 |
| `E > 20000000` | 1 |

The first position appears `num-1` times and every later position `num` times, so a list of
`N` positions has `F = num*N - 1` nodes. READ. INFERRED: `E` is in microseconds, making the
thresholds 10 s and 20 s of exposure.

R13a. Firmware 9.75, app 3.4.0 (READ): the thresholds are unchanged and the counts are raised:

| `E` | visits per position `num` |
|---|---|
| `E <= 10000000` | 4 |
| `10000000 < E <= 20000000` | 3 |
| `E > 20000000` | 2 |

Every position, including the first, is appended exactly `num` times, so the `-1` of R13 is gone
and a list of `N` positions has `F = num*N` nodes. `F` is defined as the size of the list the
planner returns ([R26](timing-and-errors.md#duration-estimate)).

R14. When the list is exhausted and more than one frame has been stacked, the device generates
a new list with the same canvas and pitch rules and continues. READ. If no next node exists
otherwise, the device clears the movement and logs an error without setting a new error code.
READ. List exhaustion is therefore neither completion nor a deadline. INFERRED.

## Movement

R15. Firmware 9.31, and firmware 9.75 (READ): for each stacked frame, star matching locates the current image on the canvas. If it is strictly less than 100 pixels from the current node, the device advances to the next node and computes the offset to it in the current frame; otherwise it computes a correction to the current node. Offsets are truncated toward zero to whole pixels. A repeated node at identical coordinates gives a zero offset. READ.

R15a. Firmware 9.75 (READ): on the first frame, if the first queued position is within 1.5 pixels (inclusive) of the canvas center (integer-divided `W/2, H/2`), one list entry is consumed before the first movement target is chosen; if that empties the list, movement is cleared. The 100-pixel test of R15 still governs later arrivals. The matching steps keep the same sequence as 9.31; whether the imported matching library behaves identically is unresolved.

R16. For the ordinary mosaic a nonzero offset `(dx, dy)` becomes one guider
[`scope_fine_move`](../../../docs/guider/methods/scope_fine_move.md) request:

```
speed = [ -dx * P / 15,  dy * P / 15 ]   (single precision)
limit = 0; backlash_comp = true
P = 206.265 * pixel_size * bin / focal_length   (double, then rounded to single)
```

READ, firmware 9.31 and 9.75; the request text and its `"limit":0,` and `"backlash_comp":true,` members are byte-identical in both. The products and the division by 15 are single precision. How the guider treats `limit` 0 is in its method page; the imager does not establish the mount-side effect. Axis semantics and signs inside the mount are outside the imager (unresolved). Each
center is not a full goto with plate solve. READ.

R17. Firmware 9.31 and 9.75: a refused or timed-out fine move (a 10,000 ms request-wait timeout; success means the reply text contains `"result":0`) is logged and
capture continues; it does not end the mosaic. READ.

A separate wide-mosaic branch moves to absolute centers with an ordinary guider
[`scope_goto`](../../../docs/guider/methods/scope_goto.md) followed by a wait for the goto (120 s
watchdog), without a plate solve per center. READ. The wide-mosaic branch is taken only when the
live stacker is the starry (wide) stacker, the session is not star-trails, and the capture type
is not the excluded one. The starry stacker is installed when the stack settings select a
starry/wide stack type, and that choice overrides the ordinary mosaic predicate. READ. Which
request selects that stack type is unresolved. If the first absolute goto fails, the stacking
worker ends with status 207. A goto or wait failure inside the branch loop records 501 and exits
the loop. READ. How either outcome reaches the client as a final code is unresolved.

## Orientation

The planner angle `A` (R8) can be replaced before the first frames initialize the canvas. Once
the canvas dimensions are initialized no recalculation happens. READ.

R18. With a solve orientation available (an equatorial-mode branch with a valid orientation),
the effective angle is the shortest signed difference, modulo 360, between `star_map_angle`
(normalized to 0..360) and the solved angle; the requested `angle` is not added. The result is
kept as a float and truncated for the planner. READ. Exact tie handling at 180 degrees is not
specified here.

R19. Without a solve orientation, a `star_map_angle` of exactly 361 means "no value" and `A` is
kept. Otherwise the device derives the angle from the local horizontal frame. READ:

```
RA_deg = RA_hours * 15
p1 = (RA_deg,         Dec_deg)
p2 = (RA_deg + 0.001, Dec_deg)        # +0.001 degree of right ascension
for each: horizontal position at the current date and observer location,
          refraction applied (library routine, constants 1010 and 10),
          azimuth := range(azimuth - 180)
dAz  = wrapped azimuth difference (extra wrap handling when abs(dAz) > 90)
dAlt = alt(p2) - alt(p1)
beta = atan2(dAlt, cos(alt(p1) / 180 * 3.14) * dAz) * 57.29577951308232
m    = range_degrees(f32(star_map_angle - beta + 180))
A    = T(f32(m))
```

The cosine uses the literal 3.14, not full-precision pi. READ.

R20. `beta` is computed from the two horizontal positions given by the small positive RA
offset at fixed declination. Subject to the coordinate library's conventions, it approximates
the horizontal bearing of that displacement. INFERRED. It is **not** established as the
direction of celestial north or of increasing declination, and no ±90-degree substitution is
implied. In the app 3.3.2 code that has been examined, `star_map_angle` is carried unchanged
from a stored plan target or a star-map selection into the request, and is 0 when no mosaic
object is present. READ. When a mosaic target is saved into a plan, the app takes the angle
from its native sky-map renderer as a float, unchanged. It normalizes the value into [0, 360)
only for display. The sky-map goto also sends a `mosaic` object (`scale`, `angle`,
`star_map_angle`) when mosaic framing is selected and the selected camera is not the telephoto
camera. There `angle` is the sky-map rotation `u` below, and `star_map_angle` is read from the
same renderer when the request is made. Auto-plan targets use 0. READ (app 3.3.2).

R20a. The sky-map renderer derives `star_map_angle` as follows. READ (app 3.3.2 native library):

```
u   = sky-map mosaic rotation in degrees, clamped to -90..90 when given to the renderer
if renderer not initialised:        value = 0
elif equatorial-mount display mode: value = u + s     # s = `angle` of the device's last
                                                      # solve result, 0 when absent
else:
  c   = sky position at the centre of the map view, as equatorial (RA, Dec)
  P1  = window pixel of c
  P2  = window pixel of (RA + 0.1 degree, same Dec)   # window x right, y down
  phi = norm360(f32(atan2(P2.y - P1.y, P2.x - P1.x) + pi) * 180/pi)
  value = norm360(u) - phi                            # not re-normalized: (-360, 360]
```

`norm360` adds or subtracts 360 until the value lies in 0..360. `phi` is the on-screen direction
of decreasing right ascension (celestial west) at the view centre, measured clockwise from
window right. So with `u` = 0, the value is 0 when west points to window right. A positive
`u` adds to the value, and a clockwise screen rotation of west subtracts from it. READ (app
3.3.2 native library). For an unmirrored sky display, `phi` is also the clockwise angle from
window up to celestial north. INFERRED.

On the device side, both branches recover `u`. In equatorial mode,
R18's difference from the solved angle leaves `u`. In the other mode, if the map is drawn with
the zenith up and azimuth increasing to the right, `phi` = 180 − `beta` and R19's `m` reduces
to `u` modulo 360. INFERRED. `star_map_angle` therefore has no fixed cardinal meaning of its
own: it carries the on-screen rotation of the sky at the moment it was read. Which way a
positive `u` turns the drawn frame on screen is not established here.

R21. `star_map_angle` is in degrees. READ (app 3.3.2 native library: the renderer converts
radians with 180/pi and wraps with 360; device arithmetic is modulo 360). A client MUST NOT
assume a universal rule such as "angle -90 gives north-south rows", nor a fixed clockwise or
counterclockwise sky rotation for a positive angle. See [R20a](#orientation).

The device-side angle logic of R18-R21 is confirmed unchanged in firmware 9.75, both the 64-bit
and 32-bit builds: identical instruction counts, only relocation differences, and the same pool
constants (0.001, 3.14, 57.29577951308232) as in firmware 9.31. READ. The sign and zero-direction
of the angle remain unresolved; this resolver pass found nothing that settles them, and a client
MUST NOT assume a direction beyond what R20/R20a already establish.
