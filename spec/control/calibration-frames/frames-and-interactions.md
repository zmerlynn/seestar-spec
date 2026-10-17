# Frames and interactions

Part of [calibration-frames](../calibration-frames.md). Requirement numbers continue across the chapter; basis and conventions are in the index.

## Bias and flat frames

```
 client                                           device
   | start_create_calib_frame {type,exp_us,adu_*} ->|  524 first, then 210/106
   |                                               |  318 / 268 / 204 / 218 / 207
   |<------------------------- result 0            |  worker started
   |<------------------------- CreateCalibFrame working (exp_us, adu, type)
   |<------------------------- CreateCalibFrame complete | fail | cancel
   | get_calib_frame {"flat"} ------------------->  |  {name, enable, ...}
   | set_calib_frame {type,name,enable} ---------> |  259 if Stack uses that type
```

R7. `start_create_calib_frame` is refused with 524 before parsing when a View function, a
ViewPlan, a planet stack, a batch stack or any mount-occupying function is active. READ.

R8. Params (object only):

- `type` absent or not a string: the automatic calibration worker runs.
- `type` = `bias`: bias. Any other string: flat. With a filter wheel the wheel position chooses
  the flat kind; an invalid position gives 207.
- `exp_us` (microseconds), `adu_min`, `adu_max` are read only when `type` is a string. A custom
  range MUST satisfy `0 <= adu_min <= adu_max <= 60000`, else 204. If either ADU key is missing,
  both take defaults (flat 10000..40000; bias 0..the dark threshold).
- `customer_library` (bool or integer) writes to the customer library; a directory may be
  created (218 on failure); a wrong type gives 106.
- `wide_cam` relays as in R3.

READ.

R9. [`CreateCalibFrame`](../../../docs/control/events/CreateCalibFrame.md) is F. On the custom
path (`type` is a string) every formatted event adds `exp_us`, `adu` and `type`; the automatic
path clears that status callback, so those members are absent. READ. `type` is `bias`,
`flat_IR`, `flat_LP` or `unknown`; `exp_us` is the exposure in microseconds; `adu` is the integer
mean raw pixel value of the latest frame. A negative requested exposure selects automatic
exposure, and later events report the chosen value. A frame whose mean is outside the requested
ADU window ends the run with 204. READ.

R9a. Wheel slots (wheel models). A custom flat takes its kind from the slot the wheel is at:
slot 1 (`IRCUT`) gives `flat_IR`, slot 2 (`LP`) gives `flat_LP`, any other slot gives 207; it
does not move the wheel. A bias moves the wheel to slot 0 (`dark`) first. The automatic worker
makes `flat_IR` at slot 1, `flat_LP` at slot 2 and then the bias at slot 0, moving the wheel
only when it is at a different slot. Each frame kind returns the wheel to its previous slot
when it ends, including on failure. READ (64-bit; the 32-bit build was not checked).

R10. No stop method dedicated to the calibration-frame worker exists. A client SHOULD stop it
with [`stop_func`](../../../docs/control/methods/stop_func.md) naming `CreateCalibFrame`; the run
then ends with `cancel`. `iscope_stop_view` cannot reach it (R6). READ (mechanism); INFERRED
(that a standalone run is reachable by name).

### Selecting frames

R11. `get_calib_frame` with no selector returns dark, bias and flat entries; with `dark`,
`bias` or `flat` it returns that type's members directly. It reports entries even when the name
is empty or the frame is disabled. 105 for a non-string selector, 209 for `light` or unknown.
READ.

R11a. Bias and flat in effect. The bias and flat applied at frame read (R6g) are loaded at
start-up and after `restore_factory_calib_frame`, from fixed file names per kind (`bias`,
`flat_IR`, `flat_LP`, each `.fit`). They are not loaded from the name that `set_calib_frame`
stores, and the frame-read step does not consult that selection. READ. The customer library is
used only when it holds a complete set: bias, IR flat and, on wheel models, LP flat. Otherwise
the default library directory is used. READ. That directory is written by
`start_create_calib_frame` without `customer_library`, and by the automatic bias that stack
start builds (R6f, R11b). READ. `get_calib_frame` reports only the stored selection, so a bias or flat
in the default directory can be in effect without being listed. READ (mechanism). Whether units
leave the factory with such files is unresolved; none ships in the firmware image. The
lens-shading correction of the wide camera on some models is separate, per-unit EEPROM data, not
a flat frame, and no method reports it
([stacking.md R6d](../stacking.md#sequence)). READ.

R11b. Automatic bias at stack start. When the main-camera process starts the Stack stage with a
fresh View worker, it runs a blocking initialisation step before stacking (order in
[stacking.md R6e](../stacking.md#sequence)). That step builds a bias when the main camera's own
`stack.wide_denoise` is on and no automatic bias has succeeded yet in this run of the imager
service. READ. The wide camera's setting is not consulted. No model, `is_stacked`, existing
file or customer-library check applies. READ. In the stack's photometry mode wide denoise is
switched off for the start, so no bias is built. READ. The done marker is set only on success
and is never cleared, so the bias is built at most once per imager run and retried on the next
start after a failure. READ. That an imager run lasts from service start to stop or reboot is
INFERRED. The bias is captured fresh: 5 frames at an exposure of 0 µs (the sensor minimum) with
the star-view gain, averaged, with the same ADU window as a custom bias (0 to the dark
threshold, else 204). READ. On wheel models the wheel moves to slot 0 (`dark`) first when it is
elsewhere and returns to its previous slot at the end (R9a). READ. The result goes straight into
the bias in effect (R11a) and is written over `bias.fit` in the default library directory with no
backup. READ. This path starts no calibration-frame worker, so no `CreateCalibFrame` event
appears; its frames raise no `Exposure` event. READ (64-bit; event search limited to the capture
calls). Its only visible traces are the `Initialise` function state and, on wheel models, the
wheel moves to slot 0 and back. READ. The step order, gate, capture parameters and done marker
are the same on the 32-bit build. READ (both builds). A failed bias ends the initialisation step early, which
skips its autofocus. READ. INFERRED: the stack then continues as after any initialisation failure. The
step ends before the `Stack` `start` event (R6e), so it cannot fall inside the stack's own
running time. READ. With wheel moves, its duration is a few seconds. INFERRED.

R11c. When a new bias or flat takes effect. Both `start_create_calib_frame` paths (custom and
automatic) build each frame directly into the in-memory frame of its kind, which frame read
(R6g) uses for every later frame. The new frame therefore takes effect as soon as that kind
finishes, not at a restart or `restore_factory_calib_frame`. READ. Only after that does the worker
write the file. `customer_library` does not change this; it only chooses the directory the file
is written to. READ. With `customer_library` and an incomplete customer set, the next start-up
loads the default directory instead (R11a), so the frame in effect and the one a restart would
load can differ. READ (mechanism). A run that fails or is stopped after capture of a kind began
(including 204, 238 and a stop) empties that kind's in-memory frame and writes no file; the
stack-start bias (R11b) behaves the same way. A 207 for an invalid wheel slot happens before
capture and leaves the frame alone. READ. INFERRED: until the next start-up or restore, frames
are then read without that kind of correction. `restore_factory_calib_frame` reloads bias,
`flat_IR` and, on wheel models, `flat_LP` from disk using the R11a rule (R14). READ (both
builds; R11a also matches on the 32-bit build).

R12. `set_calib_frame` takes `{type, name, enable}` or `[type, name, enable]`. Enabling reads the
FITS dimensions (207 if unreadable) and persists name and size. Disabling skips the FITS read
but still replaces the name. 259 while a live stack runs with the same frame type. READ.

R13. `get_calib_param` / `set_calib_param` read and store one integer per frame type, persisted
with the stack settings; meaning as a frame count is INFERRED; no range check. READ.

R14. `restore_factory_calib_frame` has the same 524 guard as R7, deletes the customer
library files, clears an in-memory dark-library lookup table and one calibration image buffer,
and reloads the bias and flat files from disk (R11a, R11c). A missing
customer directory is not an error; a failed removal gives 218 with no rollback. READ.

## Hot-pixel correction (HPC)

R15. `start_create_hpc` requires an open camera (318; also 318 when a present wheel has a
negative id). It refuses with 268 (HPC running), 206 (capture or view function working), 536
(ViewPlan running), 212 (thread). READ.

R16. The worker moves a present filter wheel to position 0, builds the correction, then tries to
restore the previous wheel position. A failed first move fails the worker with the move's error;
a failed restore does not change the result. Both moves produce ordinary
[`WheelMove`](../../../docs/control/events/WheelMove.md) events. READ. A client SHOULD expect
`WheelMove` events during HPC creation and SHOULD check the wheel position after it ends.

R17. [`CreateHPC`](../../../docs/control/events/CreateHPC.md) is F plus `hpc_num` (integer, present
when the camera-information read succeeds). The emitter and payload are READ; the `Event` value
`CreateHPC` is INFERRED from the worker's function name, not read from the emitter. Completion
time is unresolved.

R18. `wide_cam:true` on a wide-capable primary process relays the request (300 on a relay
context failure). READ.

### HPC request details

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`start_create_hpc`](../../../docs/control/methods/start_create_hpc.md) takes
`{wide_cam?}` and starts the [`CreateHPC`](../../../docs/control/events/CreateHPC.md) calibration worker. It moves a filter wheel to slot 0
and back when one is present. Errors 318, 268, 206 capture active, 536, 212. READ. Hot-pixel
calibration is INFERRED from the name.

## Function states

All three workers use the F state machine ([events/families.md](../events/families.md#f-states)):

| From | Trigger | To |
|---|---|---|
| idle | starter accepted | working |
| working | worker finished, error 0 | complete |
| working | worker error | fail (with `error`, `code`) |
| working | stop clears continuation flag | cancel (no `code`) |

READ (generic F rules). Each worker can reach `complete`, `fail` and `cancel`. Failure codes
(READ): dark 238, 249, 300, 320, 207 (R6a); calibration frame 204, 238, 249, 300, 207; HPC
218, 238, 318, 320; any of them can also fail with a filter-wheel error. INFERRED (state
mapping).

## Interactions

| Running | Blocks | Code |
|---|---|---|
| View work | `start_create_dark` | 524 (handler) or 206 (starter) |
| View, ViewPlan, planet/batch stack, mount-occupying function | `start_create_calib_frame`, `restore_factory_calib_frame` | 524 |
| capture or view function | `start_create_hpc` | 206 |
| ViewPlan | `start_create_hpc` | 536 |
| DarkLibrary worker | `start_batch_stack` | 524 |
| live Stack using the same frame type | `set_calib_frame` | 259 |

Calibration workers occupy the camera, but the exposure and view starters do not check for a
running worker. READ. A start would run alongside the worker on the same camera and is expected
to make it fail or produce invalid frames. INFERRED. A client MUST NOT start exposures or view
stages while a calibration worker runs, and SHOULD wait for its end event first.

## Errors

Chapter codes: 102, 105, 106, 204, 206, 207, 209, 210, 212, 218, 259, 268, 300, 318, 524, 536.
Relay paths can append a second error fragment (duplicate `error`/`code` members); a client
SHOULD take the first.

## Not covered or unresolved

- Meaning of `get_calib_param` values; HPC duration.
- Firmware 9.75: the selection of misplaced directories removed from the legacy root; the
  `DarkLibrary` percent logic and `start_create_dark` against 9.75 (strings and symbols exist, not
  diffed); 32-bit logic (R6m); the effect of temperature in the bright-frame threshold.
- Firmware 9.75: what schedules the periodic `Autorun/Dark/` captures (R6n), and whether they
  feed R6i's temperature comparison; which sensor-temperature reading R6i actually compares.
- Dark library: whether `start_exposure` `type:"dark"` frames pass through frame calibration; how
  the S30 board is classified (R6c, R6f "other models").
- Whether units ship with factory bias or flat files in the default library directory (R11a).
- The FITS header of the automatic stack-start bias (R11b).

## Appendix: Validating on a live device (non-normative)

1. With the view running, `start_create_dark`; expect 524.
2. Stop the view, open camera and wheel, `start_create_dark`; log `DarkLibrary` members.
3. `stop_create_dark` mid-run; confirm `cancel`.
4. `start_create_hpc` on a wheel model; log `WheelMove` before `CreateHPC complete`.
