# Dark library

Part of [calibration-frames](../calibration-frames.md). Requirement numbers continue across the chapter; basis and conventions are in the index.

## Overview

| Product | Created by | Function | Event | Selected / reset by |
|---|---|---|---|---|
| Dark library | [`start_create_dark`](../../../docs/control/methods/start_create_dark.md) | `DarkLibrary` | [`DarkLibrary`](../../../docs/control/events/DarkLibrary.md) | automatic |
| Bias / flat (and automatic set) | [`start_create_calib_frame`](../../../docs/control/methods/start_create_calib_frame.md) | calibration worker | [`CreateCalibFrame`](../../../docs/control/events/CreateCalibFrame.md) | [`set_calib_frame`](../../../docs/control/methods/set_calib_frame.md) |
| Hot-pixel correction | [`start_create_hpc`](../../../docs/control/methods/start_create_hpc.md) | `CreateHPC` | [`CreateHPC`](../../../docs/control/events/CreateHPC.md) | automatic |
| Customer library reset | [`restore_factory_calib_frame`](../../../docs/control/methods/restore_factory_calib_frame.md) | none (synchronous) | none | - |

Read-side methods: [`get_calib_frame`](../../../docs/control/methods/get_calib_frame.md),
[`get_calib_param`](../../../docs/control/methods/get_calib_param.md),
[`set_calib_param`](../../../docs/control/methods/set_calib_param.md). READ.

Frame types used here are `dark`, `bias`, `flat` (and `light`, which these methods reject with
209). READ. The `type` member of `start_create_calib_frame` is a different enum ([Bias and flat frames](frames-and-interactions.md#bias-and-flat-frames)).

## Building the dark library

```
 client                                  device
   | start_create_dark {wide_cam?} ------->|  524 (View work) / 210 (wide unsupported)
   |                                       |  318 / 268 / 206 from the starter
   |<------------------------- result 0    |  DarkLibrary worker started
   |<------------------------- DarkLibrary working (percent)
   |<------------------------- DarkLibrary complete | fail | cancel
   | stop_create_dark ------------------->|  capture error := 253, join
   |<------------------------- result 0    |
```

R1. A client MUST open the camera, and on models with a filter wheel MUST open the wheel,
before `start_create_dark`. Otherwise the starter returns 318. READ.

R2. The View-work check runs before params are parsed: active View work gives 524. The worker
starter then gives 268 if a dark worker runs and 206 if View work is active. READ. A client
SHOULD stop the view ([viewing-and-exposure.md](../viewing-and-exposure.md#starting-and-stopping-a-view))
before creating darks.

R3. `wide_cam:true` on a model that supports wide star view relays the whole request to the
wide process; on other models it gives 210. A wrong type for `wide_cam` is treated as false.
READ.

R4. [`stop_create_dark`](../../../docs/control/methods/stop_create_dark.md) sets the capture error
to 253 and joins the worker with no bounded timeout. It always returns 0 and does not relay to
the wide process. READ. The expected terminal event is `DarkLibrary` `cancel` (INFERRED from
the F rules).

R5. [`DarkLibrary`](../../../docs/control/events/DarkLibrary.md) is a function event. A separate
guider producer uses states `start`, `building`, `complete`, `fail` under the same name. READ.
Every imager `DarkLibrary` event carries `percent`, a number from 0 to 100: completed exposure
time over total exposure time, 0 before any progress. Working events are sent only when the
whole-number percentage changes, so a client MUST NOT expect one event per frame. READ. That end
states carry it too is INFERRED from the shared formatter; the guider producer's members are as
in the event card.

R6. The app also stops dark creation with `iscope_stop_view {"stage":"DarkLibrary"}`. READ
(app-sent name). That request searches only the View function's children, so it reaches only a
dark run started as part of viewing; for a standalone run it finds nothing and still replies 0.
READ. A client SHOULD stop a standalone run with `stop_create_dark` or
[`stop_func`](../../../docs/control/methods/stop_func.md) naming `DarkLibrary`. READ (mechanism);
INFERRED (that a standalone run is reachable by name).

R6a. The dark worker moves a fitted filter wheel to its dark position (slot 0) and captures five
frames at the current stack exposure. It rejects a frame whose mean is above the dark threshold
for that exposure (R6c). The first rejection in a run repeats the move to slot 0 and restarts
from that frame; a second rejection, or any rejection when no wheel is fitted, ends the run with
320. It averages the accepted frames into a master dark named by exposure and local time (R6b),
replacing older master darks for the same exposure, and then restores the previous filter slot.
READ. Failure codes: 238 (exposure), 249 (memory), 300 (frame size), 320 (bright frame not
cured by one filter retry), 207 (other). READ.

R6b. Storage. Master darks are 16-bit FITS files in a dark-library directory under the
device's private configuration area (directory `DarkLibrary`; the wide-camera process uses
`DarkLibrary_wide`). The file name is `MasterDark_<exposure>_<YYYYMMDD-hhmmss>.fit`.
Here `<exposure>` is one decimal place with unit `s`, `ms` or `us` (for example `10.0s`), and
the time is the device's local time. Sensor temperature is not part of the name. READ. Saving
a new master first deletes every library file with the same exposure prefix, so the library
holds at most one master per exposure. READ. The library is not split into factory and customer
parts: the customer library directory holds bias and flat frames only (R8, R14). READ. At
start-up, files left in an older dark-library directory on the image store are moved into the
new directory and the old directory is removed. READ. The directory is not under the image
store that the file server shares, so the masters are not reachable over HTTP or SMB. INFERRED
(from the paths). The FITS header uses the same writer as captured frames. The worker fills
exposure, the camera's current gain, sensor temperature at the end of capture, binning, filter
name and a frame count of 5. READ. Keyword names (for example `EXPTIME`, `GAIN`, `CCD-TEMP`,
`STACKCNT`) are INFERRED from the writer's keyword table.

Firmware 9.75, app 3.4.0: this legacy layout is kept for the case where the temperature library
(R6h) is not in use. When the library is in use, masters are stored as R6h1 describes. READ.

R6c. Capture settings. Before capturing, the worker sets the exposure and turns the sensor's
hot-pixel correction on. It restores the previous hot-pixel setting afterwards. It does not
change gain, so darks are taken at the camera's current gain, and frames are read with no
calibration applied. READ. The bright-frame threshold, in ADU of the frame mean, with `t` the
exposure in whole seconds:

| Model (board check) | Threshold |
|---|---|
| S50 | 500 + t × max(sensor °C, 20) |
| S50 Pro, S30 Plus-class | 5000 |
| S30 Pro: wide-camera process | 5000 |
| S30 Pro main camera, S80, other models | 2000 |

READ (the S50 Pro and S30 Pro labels are INFERRED from the board names). The S50 Pro and S30
Plus-class rows apply when the process's camera id matches the main or the wide camera id. If
neither matches, the threshold is 2000. READ.

Firmware 9.75 (64-bit), the dark-threshold reader rows: S30 Pro main camera 5000; S80 (main or wide)
5000; S50 Pro main camera with board info 11 follows a temperature formula with fixed coefficients,
about 2100 to 3200 over 0 to 30 degrees C; every other case 5000. The 32-bit threshold is unchanged
from firmware 9.31. READ. The threshold also feeds the bias maximum (R8, R11b). The 9.31 table above
applies to firmware 9.31.

The 32-bit build uses a different table. S50 uses the same formula. The 5000 threshold applies
only in the wide-camera process of the S30 Pro and S50 Pro boards. Every other case gives 2000,
including the S50 Pro main camera; there is no S30 Plus-class check. READ (32-bit). The rest of
R6a to R6e and R6g matches on the 32-bit build: the same wheel move, frame count, retry and
failure codes, storage names and directories, hot-pixel and gain handling, staleness rule and
frame-read gate. READ (both builds).

R6d. Light blocking. The only light-blocking step is the wheel move in R6a. It runs when the
process drives the main camera, on every model; that process requires an open wheel (318 from
the starter otherwise). The wide-camera process has no wheel, captures with no light-blocking
step and depends on the threshold check alone. READ. The worker does not park or move the mount.
READ. A client SHOULD cover the wide camera, or the telescope if the wheel is missing, before
creating darks. INFERRED.

R6e. Selection and reuse. At stack start the imager asks whether a usable master exists for the
current stack exposure, matched exactly to the millisecond. If the master was captured in this
session and the camera now reads above 30 °C and at least 3 °C warmer than at capture, it counts
as stale. A cooler camera does not count as stale. READ. An exposure entry that came from a library
file has no recorded temperature and is not checked; neither is any entry when the camera
temperature cannot be read. READ. If the exposure has an entry but no master in memory, the
first library file for that exposure is loaded. If the exposure has no entry, or the master is
stale, a blocking dark run starts under the Stack function. This is how stack processing starts
a `DarkLibrary` run (R5). READ. When and how library files create entries at start-up was not
traced. Gain is
not compared. READ. When it is applied, the dark must match the frame's exposure and size, or
the frame is left uncalibrated. READ.

Firmware 9.75, app 3.4.0: selection also depends on sensor temperature and the 9.31 text above
describes only the legacy path. The exposure match is unchanged: the active dark must still match
the frame's exposure within 1 ms, otherwise the frame is left uncalibrated. See R6h to R6k. READ.

R6f. When the automatic master dark runs at stack start (wire setting `auto_master_dark` in
`get_setting` / `set_setting`, persisted; `expert_mode` as in the stack settings). READ:

| Model | Automatic master dark at stack start | Dark subtracted with `stack.wide_denoise` on |
|---|---|---|
| S50 | always | never |
| S30 Plus-class, S30 Pro, S50 Pro, S80 | only when `expert_mode` and `auto_master_dark` are both on | when `auto_master_dark` is on |
| other models | only when `stack.wide_denoise` is off | never |

With `stack.wide_denoise` off, the dark is always used for calibration (R6g). `get_device_state`
`can_dark_correction` is true exactly for the models in the second row. It reports the model
check and gates nothing itself. READ. Changing `auto_master_dark` clears the live stack. READ.
With `stack.wide_denoise` on, stack start also builds a bias frame once per imager run for the
denoise path (R11b). READ.

The 32-bit build has no model check here. On every model the automatic master dark runs at
stack start only when `expert_mode` and `auto_master_dark` are both on, and with
`stack.wide_denoise` on the dark is subtracted exactly when `auto_master_dark` is on. Every model
therefore follows the second row of the table. `get_device_state` `can_dark_correction` is
always true on the 32-bit build. READ (32-bit).

Firmware 9.75, app 3.4.0: the model table above and the 32-bit paragraph no longer describe the
64-bit imager, which has no per-model gate. The temperature library is used exactly when
`stack.wide_denoise` is off or `auto_master_dark` is on (R6h). The 32-bit imager also lost the
9.31 per-model gate functions; its replacement logic was not traced, so INFERRED same as 64-bit.
In 9.75 `can_dark_correction` is a constant true on both builds. READ.

R6g. Applying calibration. Calibration is applied to a frame in place when the camera frame is
read, before the frame reaches the stacker, the preview or a save. It runs only while the
`frame_calib` setting is on. That setting is not persisted, its stored value starts false, and
`set_setting` `frame_calib` turns it on. READ. With it off, no dark, bias or flat is applied
anywhere in this path. READ. For each 16-bit frame:

1. Subtract the master dark. If no dark is used, subtract the bias frame instead. The dark
   includes bias, and bias is never subtracted together with a dark.
2. Divide by the flat. The flat has the bias subtracted when a bias is present and is
   normalised to its own mean.
3. Add a pedestal: the mean of the bias frame, or the dark's mean when there is no bias. The
   pedestal is 0 in the stack's photometry mode.
4. Round and clamp to 0..65535.

READ. Bias and flat are used only in the main-camera process. Each step is skipped when its frame
is absent. READ. Without `stack.wide_denoise`, a missing dark leaves the whole frame
uncalibrated, so flat and bias are not applied either. With `stack.wide_denoise` on and the
dark not used (R6f), bias and flat are still applied. READ. Hot-pixel correction is a sensor
control, not part of this step; turning dark correction off does not change it. READ (no
hot-pixel reference in the step); INFERRED (that the sensor applies it before readout). The
frame type selected with `set_stack_type` does not change this step. READ. Darks for the dark
library are always read raw (R6c). READ. Saved sub-frames are therefore calibrated exactly when
calibration ran on that frame. INFERRED: the save paths use the frame buffer after the in-place
step, and the path that `start_exposure` `type:"dark"` uses was not traced.

Firmware 9.75, app 3.4.0 (behaviour change): with no dark available the frame is no longer left
wholly uncalibrated. The device logs that it continues with flat and bias calibration and applies
steps 2 to 4 (flat, pedestal, clamp), and step 1 subtracts the bias instead of a dark. A dark whose
exposure differs by more than 1 ms still ends the step uncalibrated, as in 9.31. READ (64-bit).

### Temperature dark library (firmware 9.75)

R6h. The library is used when `stack.wide_denoise` is off or `auto_master_dark` is on, evaluated
at stack initialisation, frame calibration, dark creation and the refresh of R6j. At stack
initialisation the device prepares the library by the selection of R6i; a nonzero result ends
initialisation with that code. With wide denoise on, initialisation then builds the bias (R11b).
READ (64-bit).

R6h1. Storage. Root `/boot/Image/darklibrary/`, one directory per exposure named `<N>s`, with `N`
the exposure in whole seconds (for example `10s`). File name
`MasterDark_<n>_<exp>s_<T>C_<YYYYMMDD-hhmmss>.fit`: `<n>` is a positive integer, INFERRED to be the
frame count (5) and not the gain; `<exp>` has one decimal place (for example `10.0s`); `<T>` is the
sensor temperature rounded to 0.1 degree C; the time is the device's local time. READ. All three
masters OBSERVED in R6n carry `<n>` = 5, matching the frame count, and the FITS `STACKCNT` keyword
(R6n) independently reads 5 on all three; the field's meaning is still INFERRED, not READ from the
writer.

- A scanned file counts only if its name matches that pattern and its exposure matches its
  directory. `<n>` is not used as a filter. Temperature and capture time come from the file
  name. READ.
- Firmware 9.75 (64-bit): the old move of `/boot/Image/DarkLibrary` to the home ZWO folder is
  removed; the start-up step now only removes misplaced temperature directories. The 32-bit build
  still moves it. READ.
- The legacy directory of R6b is kept for the case where the library is not in use. At start-up
  the device removes `<N>s` directories that were placed inside the legacy directory by mistake;
  the selection of which directories is not traced. READ (strings and call structure).
- An SMB listing of a firmware 9.75 device's image store after a real shoot
  ([smb.md R9](../../media/smb.md#shares)) found each master dark stored as three files sharing the
  base name above: the `.fit` master, a full-size JPEG preview, and a thumbnail JPEG with a `_thn`
  suffix. `get_dark_files` (R6l) exposes only the `thn` field, not the preview. OBSERVED (file set), READ
  (naming, R6h1). Firmware 9.75, 64-bit and 32-bit builds, derives the dark catalogue's thumbnail name and checks that the file exists; this catalogue operation does not load the JPEG. The generic stored-thumbnail and stored-file services read encoded JPEG data on request when the supplied name resolves to an accepted file path. This establishes request-driven retrieval, not autonomous use of a dark preview or thumbnail as calibration input. Whether a client actually requests these dark JPEGs, and whether the catalogue's virtual names can be supplied unchanged to those services, remain unresolved. Firmware 9.31, 64-bit build, already contains the generic retrieval services. READ for the inspected catalogue and retrieval paths.
- Firmware 9.31: saving a master in this layout did not
  delete older files. Firmware 9.75 (64-bit): saving a temperature master deletes other masters of
  the same exposure whose temperature is within 0.05 degree C of the new one; masters at other
  temperatures are kept. A directory-creation or save failure is only logged and the in-memory
  dark is kept (the return value is INFERRED). READ. The legacy path still deletes the
  previous master for the same exposure. `start_create_dark` writes into the library whenever the
  library is in use. The 9.31 stale rule of R6e is not applied in this path. READ.

R6i. Selection. With `T` the sensor temperature rounded to 0.1 degree C, and only darks for the
current exposure considered, in this order. READ.

1. Exact: |dT| < 0.05 degree C.
2. Fit: a pair of darks bracketing `T`, each within 2.5 degrees C of it, combined per pixel by
   linear interpolation in 16-bit integers:
   `out = clamp(round(d1 + alpha * (d2 - d1)), 0, 65535)`, `alpha = (T - T1) / (T2 - T1)`.
3. Nearest: the closest dark within 2.5 degrees C.
4. Otherwise a blocking dark capture (`DarkLibrary` under the Stack function, as in R6e) runs and
   its result is used.

- At `T <= 0.0` degrees C a dark in the range 0.0 to 5.0 degrees C is used. If none exists the
  device logs `low_not_found` and falls back to raw denoise without a dark. READ.
- A failed temperature read gives 207; a user abort gives 253; a failed automatic capture is
  logged, raw denoise is used and the step returns success. READ.
- Gain is not part of the key. INFERRED (from the file name and the absence of a gain
  comparison).

R6j. Refresh during capture. While a Stack function runs, the device re-runs the selection before
each frame, without capturing, unless the stack exposure differs from the runtime exposure (the
previous dark is kept), the active dark is within 2.5 degrees C of the current temperature, or a
fitted dark is active and the sensor is within 0.05 degree C of the fit target. READ.

R6k. Expiry. A library dark older than 180 days (15,552,000 s) is expired. An expired exact match
is deleted and a new dark is captured. READ. Capture rules (five frames, bright-frame threshold,
filter-wheel retry, failure codes) are unchanged from R6a to R6c, except that the threshold
depends on temperature for one model (R6c). READ. Firmware 9.75: when the library is in use, a
non-abort capture failure gives 550 (`dark capture failed`); the 32-bit build matches. Hot-pixel
creation gates on the threshold for 10 s and returns 320 for a bright frame (`CreateHPC`). READ.

R6l. Reading the library: [`get_dark_files`](../../../docs/control/methods/get_dark_files.md) lists
the root (one folder entry per exposure, with a count) or one exposure directory (file entries with
exposure, date, temperature and `expired`, a string). A missing directory gives an empty list.
READ. Firmware 9.75: the request `name` may be absent, a bare string or an object with a string `name` (else 105). The root (empty or `darklibrary`) gives `path` `darklibrary` and `list_type` `folder`; `darklibrary/<N>s` (N from 1 to 2147483) gives `path` equal to the name and `list_type` `file`; any other name, or a listing failure, gives 207. The result is `{path, list_type, list}` with `list` one element `{group_name, files}`, `group_name` always empty. Folder entries are `{name, thn: "", count, type: 0, exposure_sec}`; file entries are `{name, thn, type: 1, exposure_sec, date, temperature, expired}` where `expired` is a JSON boolean (older than 180 days), `temperature` is rounded to 0.1 and files sort by temperature (0.05 tolerance) then name. An empty or unreadable directory gives `files: []`. READ (64-bit). Folder order (ascending exposure) is INFERRED. The master-dark file name is `MasterDark_<n>_<exposure>s_<temperature>C_<date>-<time>.fit`. READ. The 32-bit build has the same strings and codes; parity is INFERRED. The boolean `enable_dark_library` in `get_setting` / `set_setting` is persisted and echoed,
but no reader that changes behaviour was found; it is INFERRED inert or reserved in this build.
Setting it does not clear the stack, unlike `auto_master_dark`. READ.

R6m. The 32-bit imager of firmware 9.75 contains the same library symbols and strings,
`enable_dark_library` and `get_dark_files`. Its logic, offsets and constants were not traced.
INFERRED same as 64-bit. A spot check found the threshold, library, 550 and calibration code
equal to 64-bit; the migration differs (R6h1).

Firmware 9.75: `calc_calib_frame` copies a larger FITS header, so keywords may have been added
(unverified). The camera library `libASICamera2.so` changed in 9.75; the effect on exposure,
gain and cooling is unverified.

R6n. Live observation, firmware 9.75 (device-reported build 2975), 2026-10-17, through the
read-only tunnel proxy and a logged event stream; continues the SMB observations of
[smb.md R9](../../media/smb.md#shares). OBSERVED.

- During a ten-item ViewPlan (hourly M 33 items, Dark Correction on), three `DarkLibrary` runs
  occurred, at about 05:13–05:19, 06:30–06:36 and 08:30–08:36 UTC; the plan's 05:30, 07:30 and
  09:30 items skipped it. Each run lasted about 318 s (five 60 s frames plus overhead) and left
  exactly one new master in `darklibrary/60s/`, written at 05:18:52 (19.8 °C), 06:35:35 (14.9 °C)
  and 08:35:35 (12.1 °C) respectively. The event stream shows only a `working` state (from
  percent 0) and a terminal state, no separate `start` or `idle` state, and no control command
  preceded any of the three runs — consistent with R6e/R6i (automatic, at Stack initialisation
  after the goto). The five frames captured inside a run are not written anywhere reachable over
  SMB; only the averaged master appears.
- The run/skip pattern matches R6i's rule 3 (a master within 2.5 °C of the sensor counts as
  usable, otherwise a capture runs): the gap from the newest master's temperature to the next
  item's start was about 4.4–4.5 °C (06:30, ran) and 2.5–2.7 °C (08:30, ran), against about
  1.2–1.5 °C (07:30, skipped) and 0.7–0.9 °C (09:30, skipped). This is a first live confirmation
  of the 2.5 °C figure read in R6i. Which temperature reading is actually compared (one just
  taken, or a separately held sensor value) is unresolved.
- Separately from the dark library, the device saved an ordinary individual FITS/JPEG/thumbnail
  triple for a five-frame set under `Autorun/Dark/` about once an hour, at `:23`–`:28`, shortly
  before each plan item regardless of whether that item's `DarkLibrary` check then fired, and
  about every 15 minutes during an earlier idle stretch. Each frame carries the ordinary
  saved-frame header ([R20b](../legacy-plans-and-sequences/sequences.md#capture-run-frames)) with
  `IMAGETYP`/`FILTER` `Dark`, the stack exposure and gain, and `CCD-TEMP`; this matches the
  generic legacy per-frame save path with frame type `dark`, not the dark-library worker (which
  keeps no per-frame files, above). What schedules these captures, and whether the device reads
  their temperature for R6i's selection, are both unresolved; the cadence and timing are
  consistent with that role.
- A read-only read of all three masters' FITS headers found, common to all: `CREATOR` and
  `PRODUCER` naming the model and ZWO, an empty `PROGRAM`, `FILTER=dark`, `GAIN=200`, `EXPTIME`
  and `EXPOSURE` both 60.0, 1x1 binning (`XBINNING`/`YBINNING`/`CCDXBIN`/`CCDYBIN`), a
  2160x3840 frame, and `BITPIX` 16 with `BZERO` 32768. `CCD-TEMP` is a float32 value (19.7999992 °C
  on the first master, 14.8999996 °C on the second and 12.1000004 °C on the third) that the file
  name rounds to one decimal. OBSERVED.
  Unlike a saved dark sub (above), a master carries no `DATE-OBS`, `IMAGETYP`, `BAYERPAT`,
  `TELESCOP` or site/RA/DEC keyword; its capture time exists only in its file name. OBSERVED.
  The two later masters (14.9 °C and 12.1 °C, both written mid-shoot) also carry a full
  TAN-SIP WCS solution (`CTYPE`, `CRVAL`, `CRPIX`, `CD`, order-2 SIP terms, `IMAGEW`/`IMAGEH`)
  whose `CRVAL` sits on that session's target, while the first master (19.8 °C, written before
  the shoot started) carries none; this is consistent with stale plate-solve state from a light
  stack leaking into a dark's header on save, rather than a deliberate field. OBSERVED. A client
  MUST NOT treat WCS keywords on a master dark as meaningful.

