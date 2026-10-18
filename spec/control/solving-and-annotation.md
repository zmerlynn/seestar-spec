# Solving, goto and annotation

Scope: image analysis on the control service: plate solving, the solve-based auto goto and
goto-to-pixel flows, annotation, star finding, photometry and AI post-processing. It sits above
camera and view control ([viewing-and-exposure.md](viewing-and-exposure.md)) and uses autofocus
from [focus-and-filter.md](focus-and-filter.md). Mount motion itself (ScopeGoto, tracking) is in
the mount chapters; event framing is in [events/families.md](events/families.md). Per-method
detail stays in the catalog cards.

App names: “GoTo” is the solved goto, “Mark” is annotation, “Photometry” (and “Photometry Records”)
is photometry, and “AI Denoise” is device AI processing. The newer “AI Enhance” runs on the phone
and is not `start_ai_process`. Names are the English strings of iOS app 3.4.0; links are READ (app
call sites) unless marked.

## Conventions

As in [viewing-and-exposure.md](viewing-and-exposure.md#conventions): RFC 2119 words bind
clients; labels READ, OBSERVED, INFERRED, unresolved; READ is the 64-bit build of firmware
9.31 unless stated. A `start_*` success reply means a worker was launched.

Basis: static analysis of firmware 9.31 / app 3.3.2, with firmware 9.75 / app 3.4.0 deltas marked as such.

## Plate solving

```
 client                                 device
   | start_solve [ {ra:"<file>"} ] ------>|  210 (3PPA) / 255 (solver missing) / 212
   |<------------------------- result 0   |  solver worker started
   |<------------------------- PlateSolve start | solving | working (F)
   | get_solve_result ------------------->|  status object (may be state:"solving")
   |<------------------------- PlateSolve complete (result{...}) | fail
   | get_solve_result ------------------->|  {ra_dec, fov, focal_len, angle, image_id, state, duration_ms}
```

R1. [`start_solve`](../../docs/control/methods/start_solve.md) without a string `ra` solves the
live image; if a live solve already runs it returns 0 without a second thread. With a string
`ra` it stops any running solve synchronously and solves that stored image; an empty string
still selects this file branch. The member name `ra` is a file name, not a coordinate. No `dec`,
`path` or other key is read. READ.

R2. `start_solve` gives 210 while three-point polar alignment runs and 255 when the solver
executable is inaccessible. READ.

R3. [`stop_solve`](../../docs/control/methods/stop_solve.md) joins the solver worker with no
bounded timeout and always returns 0. READ.

R4. Result getters never start a solve:

| Method | Returns | No-data code |
|---|---|---|
| [`get_solve_result`](../../docs/control/methods/get_solve_result.md) | current status object; status-only (`state` solving/fail, `duration_ms`, `star_number`) while running or after failure | 215 when coordinates are sentinel and no star count |
| [`get_last_solve_result`](../../docs/control/methods/get_last_solve_result.md) | last cached object verbatim; may be staler | 215 when nothing cached |
| [`get_goto_solve_result`](../../docs/control/methods/get_goto_solve_result.md) | cached goto solve | 215 when cache empty (not on fail) |
| [`get_solve_obj`](../../docs/control/methods/get_solve_obj.md) | rows from the solver's intermediate star table | 207 |

READ. A client MUST check `state` in a 0-code reply; success does not mean a solution.

R5. [`PlateSolve`](../../docs/control/events/PlateSolve.md) has an F producer and a legacy
producer (`start`, `solving`, `complete`, `fail`). Members: `page`, `tag`, `star_number`,
`duration_ms`, `filename`, `result{ra_dec, fov, focal_len, angle, image_id}`, `target_ra_dec`,
`error`, `code`. READ. `ra_dec` is [right ascension in hours, declination in degrees]. For
`start_solve` it is referred to the equinox of date. READ. `fov` is [width, height] in degrees,
and `angle` is the field rotation in degrees within ±180. READ. `focal_len` is the focal length
implied by the solved field, the sensor pixel size and the binning. It is reported only when it
is between 0 and 1000. READ. It is in millimetres. INFERRED. The app
treats a PlateSolve whose `route` contains 3PPA as part of polar alignment. READ (app).

### Solve results and star detection details

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

#### Plate solve

| Method | Params | Result |
|---|---|---|
| [`start_solve`](../../docs/control/methods/start_solve.md) | optional `{ra: file name}` | 0 |
| [`stop_solve`](../../docs/control/methods/stop_solve.md) | none | 0; waits for the worker |
| [`get_solve_result`](../../docs/control/methods/get_solve_result.md) | none | SolveResult |
| [`get_last_solve_result`](../../docs/control/methods/get_last_solve_result.md) | none | cached SolveResult |
| [`get_solve_obj`](../../docs/control/methods/get_solve_obj.md) | none | up to 100 rows `[n, n, n]` |

`start_solve` returns 210 while three-point polar alignment runs and 255 when the solver is
missing. READ.

SolveResult members (READ):

| Member | Type | Present when |
|---|---|---|
| `ra_dec` | `[number, number]` | solved; RA in hours, Dec in degrees (the units and conventions below) |
| `fov` | `[number, number]` | solved; degrees (the units and conventions below) |
| `focal_len` | number | solved; millimetres, computed (the units and conventions below) |
| `angle` | number | solved; degrees, −180..180 (the units and conventions below) |
| `image_id` | integer (unsigned 16-bit) | solved |
| `state` | `complete`, `solving` or `fail` | always |
| `star_number` | integer | only if known |
| `duration_ms` | integer | always |

Units and conventions:

- `ra_dec`: the solver reports degrees; the device divides RA by 15, so RA is in hours and Dec in
  degrees. READ. The coordinates are J2000 unless the solve was configured for precession, in
  which case they are first converted to the epoch of date. READ (branch) / INFERRED (meaning of
  the flag).
- `fov`: degrees, in the order the solver prints its field size (arcminute output is divided by
  60). READ. That the order is image width then height is INFERRED.
- `focal_len`: computed by the device as the sensor's long side divided by the larger field angle
  in radians; stored only when it lies between 0 and 1000. READ (formula). Millimetres is INFERRED
  (pixel size in micrometres).
- `angle`: the solver's field rotation in degrees, normalised to −180..180. READ. That it is the
  image-up direction measured east of north is INFERRED.

`get_solve_result` returns 215 `no solve data` when there are no coordinates and no
`star_number`. A reply of `{state: "solving", star_number, duration_ms}` is a valid success. READ.
A client MUST check `state` before using coordinates.

`get_last_solve_result` returns the last cached text unchanged, or 215 when the cache is
empty. It can be stale. READ / INFERRED.

`get_solve_obj` returns stars detected in the last solve image, at most 100, read from the
solver's extraction table: its first, second and fourth columns. READ. These are taken to be x,
y (pixels) and background. INFERRED. Error 207 when the table cannot be read or has too few
columns. READ.

The solve worker can send an [`Annotate`](../../docs/control/events/Annotate.md) event (`state`, `page`, optional `tag`, `result`
holding the annotation object). READ. It does so only for annotation runs (`start_annotate`, or
the automatic annotation after a capture): `start_solve` resets the solve parameters, which
clears the annotate flag, so a solve it starts reports only through `PlateSolve`. READ.
`Annotate` carries no request id, and its `tag` is the latest tag set by any solve or
annotation; a client correlates by timing. READ / INFERRED.

## Auto goto

```
 client                                       device
   | start_auto_goto {ra, dec} ---------------->|  210 (View active) / 108 / 268 / 209 / 270 / 210
   |<------------------------- result 0         |  goto worker (function 0)
   |<------------------------- AutoGoto start | working (count, hint, target_name, ...)
   |<------------------------- ScopeGoto ... (mount)
   |<------------------------- Exposure ...; PlateSolve ...
   |<------------------------- AutoFocus ... (optional)
   |<------------------------- AutoGoto delay | working (retry, count)
   |<------------------------- AutoGoto complete | fail (error, code)
   | stop_auto_goto ------------------------->  |  capture error := 253; stop worker
```

R6. [`start_auto_goto`](../../docs/control/methods/start_auto_goto.md) is refused with 210 when
a View function is active (view mode nonzero), before parsing. A client MUST stop the view
first, or start goto through `iscope_start_view` with a target. READ.

R7. Params: two numbers as `{ra, dec}` or `[ra, dec]`; missing or non-numeric gives 108. Checks
in order: 268 (goto worker running), 209 (a coordinate within 0.1 of the sentinel -999), 270
(`below horizon`, computed altitude ≤ 0), 210 (mount unable to goto). 210 reflects the mount's
state, not the target. READ. The horizon check treats `ra` as hours (it multiplies it by 15) and
`dec` as degrees. READ. There is no other range
check on either coordinate.

R8. Success means the worker started. Mount, capture and solver failures are asynchronous and
reported by [`AutoGoto`](../../docs/control/events/AutoGoto.md) `fail` and by
[`AutoGotoStep`](../../docs/control/events/AutoGotoStep.md) (custom `fail` with `error`/`code`
on a mount error). READ.

R9. `AutoGoto` members: `count`, `hint`, `page`, `tag`, `func`, `target_name`,
`target_ra_dec`, `error`/`code`; legacy states `start`, `working`, `delay`, `complete`,
`fail`; F states as usual. Child events (ScopeGoto, Exposure, PlateSolve, AutoFocus) can arrive
before `AutoGoto` completes. READ. A client MUST NOT treat a child `complete` as goto
completion.

R10. [`stop_auto_goto`](../../docs/control/methods/stop_auto_goto.md) reads no params, sets the
capture error to 253 when the capture state allows, stops the worker (may block) and always
returns 0. It does not promise an immediate physical halt. READ. `iscope_stop_view
{"stage":"AutoGoto"}` is the view-layer equivalent.

### Goto to a pixel

Two entry points move the mount so that an image pixel becomes the centre.

| Method | Worker | View gate | Event |
|---|---|---|---|
| [`start_auto_goto_pixel`](../../docs/control/methods/start_auto_goto_pixel.md) `{x, y}` | goto worker, function 2 | none | `AutoGoto` |
| [`start_func`](../../docs/control/methods/start_func.md) `{name:"GoPixel", x, y}` | centring worker | mount-occupancy guard (203) | [`GoPixel`](../../docs/control/events/GoPixel.md) (name INFERRED) |

R11. `start_auto_goto_pixel` takes two numbers `{x, y}` or `[x, y]` (108 otherwise) and shares
the goto start helper. The same pre-checks run for every input form before the form is examined:
busy (268), the sentinel pair (-999, -999) (209), below the horizon (270) and mount unable to
goto (210). READ. 210 reflects the mount's state, not the target. READ. For pixel input the
horizon check interprets the pixel numbers as RA hours and Dec degrees. A client may therefore
see 270 for a valid pixel request. INFERRED. Pixel `x`/`y` are image pixels that the worker
converts to sky coordinates after a plate solve of the live frame. READ.

R12. `start_func` accepts only the exact name `GoPixel` (100 otherwise). `x` and `y` are
displayed-image pixels (INFERRED). The app 3.3.2 sends pixels of the unrotated wide-camera RTSP
frame, with the origin at the top-left, `x` to the right and `y` down, as integers
([goto-and-manual-motion.md R22a](mount-and-motion/goto-and-manual-motion.md#solved-goto-start_auto_goto)). READ (app
3.3.2). A missing or non-integer value makes the handler return with
neither result nor error, so the reply carries only envelope metadata. A client MUST send
integers. Other codes: 203 (mount occupied), 209 (invalid crop or wrong camera), 268, 212, 300,
207. On the main process the request may be relayed to the peer process instead. READ.

R13. The centring worker's F-family event carries `cur_pix` (two integers). READ. That this
event is named `GoPixel` is INFERRED: the name is not read from the emitter, and the request
name `GoPixel` need not equal the event name. The app 3.3.2 does listen for an event named
`GoPixel` and reads `state`, `route` and `cur_pix` from it. READ (app 3.3.2). Stop a centring run
with [`stop_func`](../../docs/control/methods/stop_func.md) `{name:"GoPixel"}` (INFERRED; the app
is seen stopping AIProcess and ViewPlan this way). The app 3.3.2 itself never sends that stop
request. READ (bounded search).

## Annotation

R14. [`start_annotate`](../../docs/control/methods/start_annotate.md) without params annotates
the image in memory; with a string (or `[string]`) it annotates that file, including an empty
string. Any other present value, including `null` or an object, gives 105. It stops a running
annotation first and may block. READ.

R15. [`get_annotate_result`](../../docs/control/methods/get_annotate_result.md) returns the cached
annotation for `img_id` (0..65534; default the most recent). 104 malformed, 204 out of range,
207 no data, 200 id not found. It may relay to the secondary process. READ. Note that code 200
is also the dispatcher's "invalid id" for a request without `id`; a client MUST disambiguate by
whether it sent an `id`.

R15a. Firmware 9.75, app 3.4.0: the `get_annotate_result` call now goes through the relay-only form of the common relay check, which relays when needed but runs no occupancy probe, so it gains no 203 or 524. Firmware 9.31 relayed through a different test. READ.

Firmware 9.75, 64-bit build: after relay and positional normalization, `get_annotate_result` accepts a file-name string directly or as the sole `file_path` member of an object. An object selects exactly one of `file_path` and `img_id`, without additional members; invalid selection gives 102. A keyed non-string file name, or a file name with an empty C-string prefix, gives 105. The file name is appended to the image-directory prefix using C-string operations, without component normalization in this handler. The cached-ID form remains available; its decoded integer ID is checked against 0..65534, with 104 for a keyed non-integer and 204 for a decoded out-of-range value. READ.

The stored-file path reads FITS/WCS data, writes temporary WCS data and invokes an annotation producer synchronously. It does not start a solve or the asynchronous annotation worker. A successful result supplies `image_size`, the producer's `annotations` fragment and boolean `wide_cam`, without `image_id`. For stored non-wide images, the imager reparses the result and, for nonempty annotation arrays, requires object items with numeric `pixelx`/`pixely` and adds `ra_dec_j2000` from stored-WCS conversion in degrees. READ. Stored wide images bypass that reparse/enrichment loop; equivalent added fields and item validation are not established for them. The field name does not independently validate the epoch of arbitrary stored WCS data.

Header/WCS failure gives 220, unsupported stored camera selector 209, and temporary WCS write failure 218. Missing annotation output/fragment and failures of the non-wide JSON/enrichment path give 207. The producer's missing-file diagnostic gives 255; producer execution failure can propagate its existing error, with 207 as fallback. READ. Firmware 9.31, 64-bit getter has no stored-file branch; its separate file-annotation starter remains distinct. Firmware 9.75, 32-bit getter also supports stored-file FITS/WCS retrieval and lacks the 64-bit helper's stored-camera-selector rejection; full result/enrichment parity remains unresolved.

R16. [`stop_annotate`](../../docs/control/methods/stop_annotate.md) joins the worker and
always returns 0. [`is_img_file_annotated`](../../docs/control/methods/is_img_file_annotated.md)
returns a boolean (false for unreadable files; 105 for a bad name). READ.

R17. [`Annotate`](../../docs/control/events/Annotate.md): F plus legacy `start`, `complete`,
`fail`; members `page`, `tag`, `result` (object), `error`/`code`. READ. The event's `result`
object differs from the `get_solve_result` object. A solve started by `start_solve` does not
emit `Annotate`. READ. `Annotate` is produced only for solves started through the annotation
entry points: `start_annotate`, and annotation requested after auto-save or exposure. READ.

R17a. `Annotate` `complete` carries `result{image_size:[w,h], annotations:[...], image_id}`.
READ. Each annotation is one of: a constellation `{type:"constell", names, points, matrix,
Ninbounds}`, a named star `{type:"star", pixelx, pixely, name, names}`, or a deep-sky object
`{type:"ngc", names, pixelx, pixely, radius}`. READ. Positions are image pixels, and `image_size`
is width then height. INFERRED. No `hd` entries occur because the device does not request them.
INFERRED. The array is produced by an external overlay tool and passed through unchanged, so
clients SHOULD tolerate unknown members.

## Find star

R18. [`start_find_star`](../../docs/control/methods/start_find_star.md) takes an optional file
name (string or `[string]`; 105 otherwise) and starts the worker; 268 if running, 212 on thread
failure. Without params it uses the current image; a supplied string, even empty, is taken as a
file name. It resets the cached result to "not done" (internal 207). READ.

R19. [`FindStar`](../../docs/control/events/FindStar.md) is an S-family event: `start`,
`complete` with `result{image_id, stars[{pixelx, pixely, radius, hfd}], pixelscale_arcsec?}`, or
`fail` with `error`/`code`. READ. `pixelscale_arcsec` is omitted when the scale query fails.
Pixel units and arcseconds per pixel are INFERRED. The app has no consumer for it.

R20. [`get_find_star_result`](../../docs/control/methods/get_find_star_result.md) succeeds only
after a completed run; otherwise it gives 207, not the worker's own status. [`stop_find_star`](../../docs/control/methods/stop_find_star.md)
joins the worker, always returns 0 and leaves the cache untouched. READ. After
`stop_find_star`, a run that had not completed ends with `FindStar` `fail`. Its code is 253 when
the stop coincided with a capture abort and 514 otherwise. A run that had already completed
reports `complete`. READ. Stopping a solve with [`stop_solve`](../../docs/control/methods/stop_solve.md)
makes the solver skip the external solve without an event of its own. READ. Whether a
`PlateSolve` failure follows is unresolved.

#### Star detection

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`start_find_star`](../../docs/control/methods/start_find_star.md) takes an optional bare
file name (no params means the current image). Errors 105, 268 already running, 212. It clears
the cached result first. READ.

Progress is a simple [`FindStar`](../../docs/control/events/FindStar.md) event: `start`, then `complete` with `result`, or `fail`
with `code` and `error`. READ.

[`get_find_star_result`](../../docs/control/methods/get_find_star_result.md) returns
`{image_id, stars: [{pixelx, pixely, radius, hfd}], pixelscale_arcsec?}`. Pixels and arcseconds
per pixel are INFERRED. Before a completed run it returns 207, whatever the worker's own error was.
READ. [`stop_find_star`](../../docs/control/methods/stop_find_star.md) waits for the worker and
keeps the cache. READ.

## Photometry

```
 client                                   device
   | check_photometry ------------------->|  318; view stage 5 started
   |<------------------------- result 0   |
   |<------------------------- CheckPhotoMetry working
   |<------------------------- CheckPhotoMetry complete (ra_dec_deg_j2000) | fail
   | get_photometry_stars {image_id?} ---->|
   | set_photometry {id, save, name?} ---->|
   | get_photometry_result -------------->|  {path, files}
```

R21. [`check_photometry`](../../docs/control/methods/check_photometry.md) starts view stage 5,
which stops the current view stage ([viewing-and-exposure.md](viewing-and-exposure.md#view-stages-started-directly)).
Only 318 and thread errors are immediate. The worker sets camera exposure control 1 to 2000000
(READ). Exposure (control 1) is expressed in microseconds, so this is a 2-second exposure; the unit
is INFERRED from the camera library's conversion of the value to sensor lines
([viewing-and-exposure R17b](viewing-and-exposure.md#camera-and-isp-settings)). The worker then captures, solves and validates the target position.
Its failures (238 exposure, 251 solve, 204 outside image, 253 aborted, 300) are function status
in events, not reply codes. READ.

R21a. Firmware 9.75, app 3.4.0: `check_photometry` accepts optional numbers `magV` (default 13.0)
and `offsetDeg` (default 2.5, degrees INFERRED); a non-number gives 102, `offsetDeg` of 0 or less
gives 204, and a non-object `params` gives 107. The worker may now download reference stars when the
internet is reachable. Firmware 9.31 reads no parameters. READ.

R21b. Firmware 9.75, app 3.4.0 (64-bit build): the reference-star download in R21a is an outbound
HTTP(S) request from the device to a vendor catalogue service when photometry is requested. The
response must be a JSON object with `code` and `msg` members and a `data` object holding an
`items` array; an invalid query (RA, Dec, magnitude or offset), an oversized response, an HTTP
error or a nonzero `code` aborts the download. The result is written to the reference-star file
through a temporary file and a rename (9.31 saved the same file directly). Firmware 9.75 D64 and D32: on the download branch, the device constructs an HTTPS GET to a fixed reference-star catalogue-service route. Its numeric query fields are `decDeg`, `magV`, `offsetDeg` and `raDeg`, in that order. The solved center supplies Dec and RA in degrees, with solved RA multiplied by 15; the photometry query supplies the magnitude and angular-offset parameters, defaulting to 13 and 2.5. Both builders use the classic locale and precision 17, with a 5-second connection timeout, 30-second read/write timeouts and a 2-MiB response cap. They reject nonfinite query values, RA outside `[0,360)`, Dec outside `[-90,90]` and nonpositive offset; no additional magnitude interval is checked here. This caller supplies no custom headers or account/remote-join credential. Firmware 9.31 D64 and D32 lack this fetch in the corresponding photometry worker. READ. The operational service address is omitted. Exact cross-library formatting for every value, successful delivery, server acceptance, authorization policy and catalogue semantics remain unresolved. READ for the structure.
A client takes no part in the fetch, and the device needs internet access for it.

R22. [`CheckPhotoMetry`](../../docs/control/events/CheckPhotoMetry.md) is F; `ra_dec_deg_j2000`
(two numbers, degrees J2000, INFERRED) is added only at `complete`. READ. Firmware 9.75, app 3.4.0:
the formatter also adds a boolean `has_download_ref_star` at the same state check (raw `true` or
`false`, reporting a stored flag, which is the outcome of the download in R21b; the exact condition
that sets it was not traced). The member is absent in firmware 9.31. READ for existence and place.

R23. Star and result methods:
[`get_photometry_stars`](../../docs/control/methods/get_photometry_stars.md) `{image_id?}` (104,
207, 200); [`get_photometry_plot`](../../docs/control/methods/get_photometry_plot.md) `{id}`
(a string; 104, 207); [`get_saved_photometry_stars`](../../docs/control/methods/get_saved_photometry_stars.md)
returns `{PhometryStars:[...]}` (the misspelling is on the wire);
[`set_photometry`](../../docs/control/methods/set_photometry.md) `{id, save, name?}` (104, 106,
105, 207 for an unknown id); it changes only cached plot state and does not
write a file. [`get_photometry_result`](../../docs/control/methods/get_photometry_result.md)
returns a relative folder and file list. READ. Firmware 9.75, 64-bit build (READ): each object in `get_photometry_result`'s `result.files` array carries boolean `is_variable` beside `star_name` and `has_ra_dec_deg_j2000`. It is derived through the saved CSV's named `Is Variable` column and the file-summary parser, and is false when the selected summary lacks valid coordinates. Each `get_saved_photometry_stars` entry in `PhometryStars` also carries `is_variable`, from cached plot state. The per-star objects carried by `get_photometry_stars` and `get_photometry_plot` include boolean `is_variable` and `is_overexposure`. In the traced Bayer-image measurement path, `is_overexposure` is set when a tested aperture sample in the half-size, 16-bit green image is greater than 65000; equality alone does not set it. An overexposed star's `measure_mag` is null, and other measurement-validity checks can also produce null. Firmware 9.75, 32-bit build (READ): the per-star serializer emits the same two boolean keys, and a local detector comparison also uses a strict 65000 threshold. Complete 32-bit detector-to-result parity and mixed/malformed CSV summary selection remain unresolved. The three corresponding key/column strings are absent from the supplied firmware 9.31 binaries on both builds (READ).

R23a. Firmware 9.75, app 3.4.0: [`get_photometry_result_json`](../../docs/control/methods/get_photometry_result_json.md)
`{name}` returns the rows of one saved photometry CSV (`name` must start with `Magnitude_`, end with
`.csv` and contain no slash; 105 non-string, 102 other violations, 255 not accessible, 258 cannot be
opened). It returns `{path, name, rows}`; each row carries the identity, reference and measured
magnitudes, pixel position, exposure times (text, Julian and modified Julian dates), `is_variable` and
`snr`, with empty numbers sent as `null`. It is a different method from `get_photometry_result`.
[`get_photometry_wcs`](../../docs/control/methods/get_photometry_wcs.md) takes no parameters and
returns the image size and the linear WCS terms of the photometry image (267 when there is no
photometry image, 207 when the WCS keys are incomplete). Both are read only. READ. The 32-bit build
has the same helpers; the 267 path there is not confirmed.
 A full stop of the Stack stage may clear
photometry data (READ, from `iscope_stop_view`).

## AI processing

R24. [`start_ai_process`](../../docs/control/methods/start_ai_process.md) requires numeric
`brightness`, `contrast`, `saturation` (108, checked in that order); optional `name` (105),
`crop` (up to eight integers; 102/104) and `dbe` (even-length integer list; 102). It stops a
previous AI worker, loads the image and starts the `AIProcess` worker. The app's `sharp` member
is not read. A local success returns `{estimated_sec}`, an estimate computed from the image
size before the worker starts, not a completion state. On wide models the request may be relayed
before validation, and the peer's reply is returned. READ.

R25. [`check_ai_process`](../../docs/control/methods/check_ai_process.md) reads only `name`
(105) and `crop` (102/104), tests a mosaic image for black gaps after the optional crop and returns
`gap_ok`. A non-mosaic image or an unreadable image gives `gap_ok:true` rather than an error. It starts nothing and emits no event. READ.

R26. [`AIProcess`](../../docs/control/events/AIProcess.md) is F. READ. A `complete` may also
carry `ori_name` and `dst_name` (INFERRED; formatter read, binding to this event not). Stop with
[`stop_func`](../../docs/control/methods/stop_func.md) `{name:"AIProcess"}`; `stop_func`
reports success whether or not the function was running, then relays the request to the peer
process. The local stop is not undone if the relay fails. A missing or non-string `name` gives
105; a relay context failure gives 300 in a reply without `jsonrpc`, `Timestamp`, `method` or
`result`. READ.

Firmware 9.31 and firmware 9.75, 64-bit builds: `get_solve_result` ignores params and reports current solve data without starting a solve. If both coordinate components satisfy `abs(value+999)>0.1`, it formats `state:"complete"`, `ra_dec`, `fov`, `focal_len`, `angle` and `image_id`; this is a sentinel test, not general coordinate validation. Otherwise it formats `state:"solving"` while the solve worker runs and `state:"fail"` when it does not. `star_number` is included when its stored value differs from -1, and `duration_ms` is always formatted. The RPC returns that object when the coordinate test passes or a star count is available; otherwise it returns 215. READ. The changed firmware 9.75 internal layout does not establish a changed wire contract. Full 32-bit formatter parity remains unresolved.

R27. [`upload_refstar_info`](../../docs/control/methods/upload_refstar_info.md) requires an
object (107; positional arrays are refused) with `refData`, an array; the literal key
`refData:` (with the trailing colon) is read only when `refData` is absent, and a wrong-typed `refData` does not fall back (102 when neither is an array). READ.
The array is not parsed: it is serialised unchanged and written, replacing any previous copy,
as the reference-star file in the AI-processing temporary directory, which is created if
needed. READ. Failure to create the directory gives 257, failure to open the file gives 258,
and a failed write or sync gives 218, each as the method's error. READ (firmware 9.31). Firmware 9.75: the handler gives 107 and 102 (also when `refData` is not an array) and calls a save helper that writes `ref_stars.json` to a
temporary file named with the process id and then renames it; a rename failure removes the temporary file and gives 515. The 257, 258 and 218 codes remain, coming from the directory check and the file write helpers inside the save helper (no code is set in the save helper itself, so the helper's code is returned). READ (64-bit). The `refData:` alias is also present in firmware 9.31. The 32-bit build has the temporary-file string; codes there are INFERRED the same. The app sends a list of
its nearby-star records here (READ, app 3.3.2); the element shape is the app's and is not
enforced by the device. The file is consumed by the device's own stacking worker: in the
photometry stacking mode it loads the file as the reference-star list. READ. That this mode is
the photometry/check stack mode is INFERRED.

### AI processing and relay

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`start_ai_process`](../../docs/control/methods/start_ai_process.md) takes
`{name?, crop?, brightness, contrast, saturation, dbe?}`. `brightness`, `contrast` and
`saturation` are required numbers (108). `crop` is up to eight integers (four corner points,
INFERRED); `dbe` is an even-length integer array (102 otherwise). `sharp` is not read. READ. The
reply is `{estimated_sec}`. The worker is the [`AIProcess`](../../docs/control/events/AIProcess.md) function; at completion it reports
`ori_name` and `dst_name`. READ. Stop it with `stop_func {name: "AIProcess"}`. READ.

[`check_ai_process`](../../docs/control/methods/check_ai_process.md) takes `{name?, crop?}`
and returns `{gap_ok}`. It is true when the image is not a mosaic, or when the image cannot be
loaded. READ. A client MUST NOT read true as "image checked". It is not a signal that a
mosaic finished its centers ([mosaic error propagation](mosaic/timing-and-errors.md#error-propagation)). INFERRED.
Firmware 9.75: both methods call the relay-to-slave check in its type-0 form, which only decides
whether to relay to the wide process and never returns 203 or 524 ([relay routing R31a](session-handshake/relay-routing.md#second-camera-relay-routing)). READ.

In dual-camera routes both methods may be relayed to the wide process. READ.

## Interactions

| Running | Blocks or stops | Code / effect |
|---|---|---|
| any View function | `start_auto_goto` | 210 |
| goto worker | second `start_auto_goto` / `start_auto_goto_pixel` | 268 |
| 3PPA | `start_solve` | 210 |
| mount occupied | `start_func GoPixel` | 203 |
| `start_solve` with file | stops the running solve | synchronous |
| `start_annotate` | stops the running annotation | synchronous |
| `check_photometry` | stops the current view stage | asynchronous |
| `start_ai_process` | stops the previous AI worker | may block |

## Errors

Chapter codes: 100, 102, 104, 105, 106, 107, 108, 200, 203, 204, 207, 209, 210, 212, 215, 218,
238, 251, 253, 255, 257, 258, 268, 270, 300, 318, 514. 238, 251, 253 and 514 appear only as worker status in events here.

## Not covered or unresolved

- Units of SolveResult `ra_dec`, `fov`, `focal_len`, `angle`.
- Columns of `get_solve_obj`.

- Firmware 9.75: the reference-star download address and the condition behind `has_download_ref_star` and `is_overexposure` (R21b to R23).

- `ra_dec` units for producers other than `start_solve`. (The block-solve path's epoch choice per
  caller is in [mount-and-motion.md R12](mount-and-motion.md#common-rules-for-guider-calls).)
- Which F states each worker reaches; event after `stop_annotate`; whether a `PlateSolve`
  failure follows `stop_solve`.
- Pixel origin and axis direction for `start_auto_goto_pixel`.
- `get_solve_obj` column meanings; the centring event name and its stop path.
- Relay failure behaviour for `get_annotate_result` and AI methods.
- Firmware 9.75: validation of the `file_path` member of `get_annotate_result`, and where `is_variable` sits in the `get_photometry_result` entries.

## Appendix: Validating on a live device (non-normative)

1. `start_solve`, poll `get_solve_result` every second; record `state` transitions and the
   `PlateSolve` order against them.
2. With a view running, `start_auto_goto`; expect 210.
3. `start_find_star` then `get_find_star_result` before `FindStar complete`; expect 207.
